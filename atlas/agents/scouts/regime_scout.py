"""
RegimeScout — Real-time Market Regime Intelligence Agent.

Detects:
- Volatility regimes (low_vol, normal_vol, high_vol, panic_vol)
- Trend regimes (trending_up, trending_down, mean_reverting, choppy)
- Liquidity regimes (deep_liquid, normal, thin, dangerous)
- Compression/expansion patterns
- Abnormal market activity

RUN INTERVAL: 60 seconds

Integrations:
- Ideator: regime-aware strategy generation
- Mutator: regime-conditioned mutation selection
- Validator: dynamic validation thresholds based on regime
- Execution: adaptive slippage based on volatility regime
"""

import asyncio
import json
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.core.scout_contracts.scout_contract import (
    RegimePayload,
    SCOUT_CHANNELS,
    scout_summary_for_ideator,
)


class RegimeScout(BaseAgent):
    """
    Real-time market regime classifier.
    Polls market_data_l1 every 60s and persists regime intelligence.
    """

    name = "RegimeScout"
    agent_type = "scout"
    layer = "L1"

    # Standard run interval
    RUN_INTERVAL_SECONDS = 60

    # Volatility thresholds (percentiles)
    VOL_LOW_PCT = 33
    VOL_HIGH_PCT = 66
    VOL_PANIC_PCT = 95

    # Trend strength thresholds
    TREND_STRONG = 0.003
    TREND_WEAK = 0.001

    # RVOL thresholds
    RVOL_LOW = 0.7
    RVOL_HIGH = 1.5

    # Bollinger compression (band width as % of mid)
    COMPRESSION_THRESHOLD = 0.02       # 2% band width = compressed
    EXPANSION_THRESHOLD = 0.08         # 8% band width = expanding

    # Minimum bars for meaningful computation
    MIN_BARS = 30

    def __init__(
        self,
        redis_client: Redis,
        db_client: TimescaleClient,
        symbols: Optional[list[str]] = None,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.messaging = MessagingClient(redis_client)

        # Default symbols to analyze
        self.symbols = symbols or [
            "BTCUSDT", "ETHUSDT", "SOLUSDT",
            "SPY", "QQQ", "AAPL", "MSFT", "NVDA",
        ]

        # Cache last payload for Ideator consumption
        self._latest_payload: Optional[RegimePayload] = None

    async def run(self):
        logger.info(f"{self.name} started — monitoring {len(self.symbols)} symbols")
        while self.status == "running":
            try:
                for symbol in self.symbols:
                    await self._analyze_symbol(symbol)
                # Publish summary to Ideator channel
                await self._publish_summary()
            except Exception as e:
                logger.error(f"{self.name} cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _analyze_symbol(self, symbol: str) -> Optional[RegimePayload]:
        """Analyze a single symbol and persist intelligence."""
        try:
            df = await self.db.fetch_recent_bars(symbol, limit=500)
            if df is None or len(df) < self.MIN_BARS:
                logger.debug(f"{self.name}: {symbol} — insufficient data ({len(df) if df is not None else 0} bars)")
                return None

            # Compute all regime classifications
            payload = self._classify_regime(df, symbol)

            # Persist to DB
            await self._persist(payload)

            # Publish to Redis
            await self._publish(payload)

            # Cache latest for Ideator
            self._latest_payload = payload

            logger.info(
                f"{self.name}: {symbol} → vol={payload.volatility_regime}, "
                f"trend={payload.trend_regime}, "
                f"compression={'YES' if payload.compression_detected else 'no'}"
            )
            return payload

        except Exception as e:
            logger.warning(f"{self.name}: Error analyzing {symbol}: {e}")
            return None

    def _classify_regime(self, df: pd.DataFrame, symbol: str) -> RegimePayload:
        """Core regime classification logic."""
        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        # --- Volatility Regime ---
        # ATR as % of close
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
        atr_pct = atr / close[-1] * 100 if close[-1] > 0 else 0

        # Realized vol (rolling 20-bar std of returns)
        returns = np.diff(np.log(close + 1e-10))
        realized_vol = np.std(returns[-20:]) * np.sqrt(252 * 390) if len(returns) >= 20 else np.std(returns) * np.sqrt(252 * 390)

        # Classify volatility
        if realized_vol > np.percentile(returns, self.VOL_PANIC_PCT) * np.sqrt(252 * 390) * 2:
            vol_regime = "panic_vol"
        elif len(close) > 30:
            # Build ATR percentile distribution from history
            atr_pct_series = []
            for i in range(14, min(len(close), len(tr) + 14)):
                if i >= len(close):
                    break
                window_start = max(0, i - 14)
                window_end = min(len(tr), i + 1)
                if window_end > window_start:
                    avg_tr = np.mean(tr[window_start:window_end])
                    atr_pct_series.append(avg_tr / close[i] * 100)
            if atr_pct_series:
                high_threshold = np.percentile(atr_pct_series, self.VOL_HIGH_PCT)
                low_threshold = np.percentile(atr_pct_series, self.VOL_LOW_PCT)
                if atr_pct > high_threshold:
                    vol_regime = "high_vol"
                elif atr_pct < low_threshold:
                    vol_regime = "low_vol"
                else:
                    vol_regime = "normal_vol"
            else:
                vol_regime = "normal_vol"
        else:
            # Fallback for insufficient history
            if atr_pct > 2.0:
                vol_regime = "high_vol"
            elif atr_pct < 0.5:
                vol_regime = "low_vol"
            else:
                vol_regime = "normal_vol"

        # --- Trend Regime ---
        ema_12 = self._ema(close, 12)
        ema_26 = self._ema(close, 26)
        sma_20 = self._sma(close, 20)
        ema_spread = (ema_12 - ema_26) / max(close[-1], 1e-10)
        price_vs_sma = (close[-1] - sma_20) / max(sma_20, 1e-10)

        if ema_spread > self.TREND_STRONG and price_vs_sma > 0:
            trend_regime = "trending_up"
        elif ema_spread < -self.TREND_STRONG and price_vs_sma < 0:
            trend_regime = "trending_down"
        elif abs(ema_spread) < self.TREND_WEAK and abs(price_vs_sma) < self.TREND_WEAK:
            trend_regime = "choppy"
        else:
            trend_regime = "mean_reverting"

        # --- Liquidity Regime (from RVOL) ---
        avg_volume = np.mean(volume[-50:]) if len(volume) >= 50 else np.mean(volume)
        rvol = volume[-1] / max(avg_volume, 1)

        if rvol > self.RVOL_HIGH * 1.5:
            liq_regime = "deep_liquid"
        elif rvol > self.RVOL_HIGH:
            liq_regime = "normal"
        elif rvol > self.RVOL_LOW:
            liq_regime = "thin"
        else:
            liq_regime = "dangerous"

        # --- Compression / Expansion ---
        bb_upper = self._sma(close, 20) + 2 * np.std(close[-20:]) if len(close) >= 20 else close[-1] * 1.02
        bb_lower = self._sma(close, 20) - 2 * np.std(close[-20:]) if len(close) >= 20 else close[-1] * 0.98
        bb_width = (bb_upper - bb_lower) / max(close[-1], 1e-10)

        compression = bool(bb_width < self.COMPRESSION_THRESHOLD)
        expansion = bool(bb_width > self.EXPANSION_THRESHOLD)

        # --- VWAP Deviation ---
        vwap = np.sum(close * volume) / max(np.sum(volume), 1)
        vwap_dev = (close[-1] - vwap) / max(vwap, 1e-10) * 100

        # --- Confidence Score ---
        confidence = min(1.0, len(close) / 500)

        # --- Correlation regime (simplified: uses RRG-style cross-asset heuristic) ---
        if "BTC" in symbol or "ETH" in symbol:
            corr_regime = "clustered"
        elif vol_regime == "panic_vol":
            corr_regime = "panic_correlation"
        else:
            corr_regime = "diversified"

        # Build ATR percentile
        atr_percentile = 50.0  # default
        if len(tr) >= 50:
            atr_series = [np.mean(tr[max(0, i-14):i+1]) for i in range(14, len(tr))]
            atr_percentile = (sum(1 for a in atr_series if a <= atr) / len(atr_series)) * 100

        # Determine correlation regime for metadata
        asset_class = "crypto" if "USDT" in symbol else "equity"

        return RegimePayload(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            asset_class=asset_class,
            timeframe="1m",
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            liquidity_regime=liq_regime,
            correlation_regime=corr_regime,
            atr_percentile=atr_percentile,
            realized_volatility=round(realized_vol, 6),
            relative_volume=round(rvol, 4),
            spread_bps=0.0,  # L2 data not available yet
            compression_detected=compression,
            expansion_detected=expansion,
            vwap_deviation_pct=round(vwap_dev, 4),
            confidence_score=round(confidence, 4),
        )

    async def _persist(self, payload: RegimePayload):
        """Insert regime intelligence row into market_regime_memory."""
        query = """
            INSERT INTO market_regime_memory (
                symbol, asset_class, timeframe, timestamp,
                volatility_regime, trend_regime, liquidity_regime, correlation_regime,
                atr_percentile, realized_volatility, relative_volume, spread_bps,
                compression_detected, expansion_detected, vwap_deviation_pct,
                confidence_score, metadata
            ) VALUES (
                :symbol, :asset_class, :timeframe, :timestamp,
                :volatility_regime, :trend_regime, :liquidity_regime, :correlation_regime,
                :atr_percentile, :realized_volatility, :relative_volume, :spread_bps,
                :compression_detected, :expansion_detected, :vwap_deviation_pct,
                :confidence_score, :metadata
            )
        """
        params = {
            "symbol": payload.symbol,
            "asset_class": payload.asset_class,
            "timeframe": payload.timeframe,
            "timestamp": payload.timestamp,
            "volatility_regime": payload.volatility_regime,
            "trend_regime": payload.trend_regime,
            "liquidity_regime": payload.liquidity_regime,
            "correlation_regime": payload.correlation_regime,
            "atr_percentile": payload.atr_percentile,
            "realized_volatility": payload.realized_volatility,
            "relative_volume": payload.relative_volume,
            "spread_bps": payload.spread_bps,
            "compression_detected": payload.compression_detected,
            "expansion_detected": payload.expansion_detected,
            "vwap_deviation_pct": payload.vwap_deviation_pct,
            "confidence_score": payload.confidence_score,
            "metadata": json.dumps(payload.metadata),
        }
        await self.db._execute_insert(query, params)

    async def _publish(self, payload: RegimePayload):
        """Publish regime intelligence to Redis channel."""
        channel = SCOUT_CHANNELS["market_regime_updates"]
        await self._redis.publish(channel, json.dumps(payload.to_dict()))

    async def _publish_summary(self):
        """Publish a compressed regime summary for Ideator consumption."""
        if self._latest_payload is None:
            return
        summary = scout_summary_for_ideator(regime=self._latest_payload)
        await self._redis.set("scout:regime_summary", summary, ex=120)

    def get_latest(self) -> Optional[RegimePayload]:
        """Return cached latest payload for cross-agent consumption."""
        return self._latest_payload

    # ------------------------------------------------------------------
    # Technical Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> float:
        if len(values) < period:
            return float(np.mean(values))
        multiplier = 2 / (period + 1)
        ema = float(np.mean(values[:period]))
        for v in values[period:]:
            ema = (v - ema) * multiplier + ema
        return ema

    @staticmethod
    def _sma(values: np.ndarray, period: int) -> float:
        if len(values) < period:
            return float(np.mean(values))
        return float(np.mean(values[-period:]))
