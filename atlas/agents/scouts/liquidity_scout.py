"""
LiquidityScout — Real-time Liquidity Intelligence Agent.

Measures:
- Average spread (bps)
- Depth imbalance (bid volume / ask volume)
- Liquidity score (0-100 aggregate)
- Slippage risk (0-1)
- Market impact estimate
- Liquidity regime classification

RUN INTERVAL: 120 seconds

Integrations:
- ExecutionGateway: widen slippage in thin liquidity, reject dangerous environments
- Ideator: discourage high-frequency churn in thin liquidity
- Validator: increase cost stress testing in thin markets
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
    LiquidityPayload,
    SCOUT_CHANNELS,
    scout_summary_for_ideator,
)


class LiquidityScout(BaseAgent):
    """
    Real-time liquidity monitor.
    Uses market_data_l2 (orderbook data) and order_flow to assess execution liquidity.
    Falls back to volume-based heuristics when L2 data is unavailable.
    """

    name = "LiquidityScout"
    agent_type = "scout"
    layer = "L1"

    RUN_INTERVAL_SECONDS = 120

    # Liquidity score thresholds
    LIQ_EXCELLENT = 80
    LIQ_STABLE = 60
    LIQ_THIN = 40
    LIQ_DANGEROUS = 0

    # Spread thresholds (bps)
    SPREAD_EXCELLENT = 1.0
    SPREAD_STABLE = 5.0
    SPREAD_THIN = 20.0

    # Depth imbalance thresholds
    IMBALANCE_THRESHOLD = 0.3  # |1 - ratio| > this = dangerous imbalance

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

        self.symbols = symbols or [
            "BTCUSDT", "ETHUSDT", "SOLUSDT",
            "SPY", "QQQ", "AAPL", "MSFT", "NVDA",
        ]

        self._latest_payload: Optional[LiquidityPayload] = None

    async def run(self):
        logger.info(f"{self.name} started — monitoring {len(self.symbols)} symbols")
        while self.status == "running":
            try:
                for symbol in self.symbols:
                    await self._analyze_liquidity(symbol)
                await self._publish_summary()
            except Exception as e:
                logger.error(f"{self.name} cycle error: {e}")
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _analyze_liquidity(self, symbol: str) -> Optional[LiquidityPayload]:
        """Analyze liquidity for a single symbol."""
        try:
            # Try L2 data first (orderbook snapshots)
            l2_data = await self._fetch_l2_data(symbol)

            if l2_data is not None:
                return await self._analyze_with_l2(symbol, l2_data)

            # Fallback: volume-based liquidity estimation
            return await self._analyze_volume_based(symbol)

        except Exception as e:
            logger.warning(f"{self.name}: Error analyzing {symbol} liquidity: {e}")
            return None

    async def _fetch_l2_data(self, symbol: str) -> Optional[dict]:
        """Fetch latest orderbook snapshot from market_data_l2."""
        try:
            query = """
                SELECT time, bids, asks, spread, mid_price
                FROM market_data_l2
                WHERE symbol = :symbol
                ORDER BY time DESC
                LIMIT 1
            """
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text(query), {"symbol": symbol})
                row = result.fetchone()
                if row:
                    return {
                        "time": row[0],
                        "bids": json.loads(row[1]) if isinstance(row[1], str) else row[1],
                        "asks": json.loads(row[2]) if isinstance(row[2], str) else row[2],
                        "spread": float(row[3]),
                        "mid_price": float(row[4]),
                    }
            return None
        except Exception:
            return None

    async def _analyze_with_l2(self, symbol: str, l2: dict) -> LiquidityPayload:
        """Analyze liquidity using orderbook data."""
        spread_bps = l2["spread"] / max(l2["mid_price"], 1e-10) * 10000 if l2["mid_price"] > 0 else 0

        # Depth imbalance
        bids = l2.get("bids", {})
        asks = l2.get("asks", {})

        bid_volume = sum(float(v) for v in bids.values())
        ask_volume = sum(float(v) for v in asks.values())
        depth_imbalance = bid_volume / max(ask_volume, 1)

        # Slippage risk: wider spreads + imbalance = higher risk
        spread_risk = min(1.0, spread_bps / 100)
        imbalance_risk = min(1.0, abs(1.0 - depth_imbalance)) if depth_imbalance > 0 else 0.5
        slippage_risk = round((spread_risk * 0.6 + imbalance_risk * 0.4), 4)

        # Market impact estimate: slippage_risk * mid_price * 0.01
        impact_estimate = slippage_risk * l2["mid_price"] * 0.01

        # Liquidity score (0-100)
        liq_score = max(0, min(100,
            100 - (spread_bps * 3) - (abs(1 - depth_imbalance) * 20)
        ))

        # Classification
        if liq_score >= self.LIQ_EXCELLENT:
            regime = "excellent"
        elif liq_score >= self.LIQ_STABLE:
            regime = "stable"
        elif liq_score >= self.LIQ_THIN:
            regime = "thin"
        else:
            regime = "dangerous"

        payload = LiquidityPayload(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            avg_spread_bps=round(spread_bps, 4),
            depth_imbalance=round(depth_imbalance, 4),
            liquidity_score=round(liq_score, 2),
            slippage_risk=slippage_risk,
            market_impact_estimate=round(impact_estimate, 6),
            liquidity_regime=regime,
        )

        await self._persist(payload)
        await self._publish(payload)
        self._latest_payload = payload

        logger.info(
            f"{self.name}: {symbol} → liq={regime}, score={liq_score:.0f}, "
            f"spread={spread_bps:.2f}bps, imbalance={depth_imbalance:.2f}"
        )
        return payload

    async def _analyze_volume_based(self, symbol: str) -> LiquidityPayload:
        """Fallback: estimate liquidity from volume patterns when L2 unavailable."""
        bars = await self.db.fetch_recent_bars(symbol, limit=100)
        if bars is None or len(bars) < 20:
            return None

        volumes = bars["volume"].values.astype(float)
        close = bars["close"].values.astype(float)

        # Use RVOL as liquidity proxy
        avg_vol = np.mean(volumes)
        rvol = volumes[-1] / max(avg_vol, 1)
        vol_std = np.std(volumes) / max(avg_vol, 1)

        # Estimate spread from volatility (inverse of liquidity)
        returns = np.diff(np.log(close + 1e-10))
        vol_estimate = np.std(returns[-20:]) if len(returns) >= 20 else np.std(returns)
        estimated_spread_bps = vol_estimate * 10000 * 0.5  # half of vol as spread proxy

        # Liquidity score heuristic
        if rvol > 1.5 and vol_std < 0.5:
            liq_score = 85
            regime = "excellent"
        elif rvol > 1.0 and vol_std < 1.0:
            liq_score = 65
            regime = "stable"
        elif rvol > 0.5:
            liq_score = 40
            regime = "thin"
        else:
            liq_score = 20
            regime = "dangerous"

        payload = LiquidityPayload(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            avg_spread_bps=round(estimated_spread_bps, 4),
            depth_imbalance=1.0,
            liquidity_score=round(liq_score, 2),
            slippage_risk=round(max(0, min(1, 1 - rvol)), 4),
            market_impact_estimate=round(estimated_spread_bps * close[-1] / 10000, 6),
            liquidity_regime=regime,
            metadata={"method": "volume_heuristic", "rvol": round(float(rvol), 4)},
        )

        await self._persist(payload)
        await self._publish(payload)
        self._latest_payload = payload

        logger.info(
            f"{self.name}: {symbol} → liq={regime} (volume heuristic), score={liq_score:.0f}"
        )
        return payload

    async def _persist(self, payload: LiquidityPayload):
        """Insert liquidity intelligence into liquidity_intelligence table."""
        query = """
            INSERT INTO liquidity_intelligence (
                symbol, timestamp,
                avg_spread_bps, depth_imbalance, liquidity_score,
                slippage_risk, market_impact_estimate, liquidity_regime,
                metadata
            ) VALUES (
                :symbol, :timestamp,
                :avg_spread_bps, :depth_imbalance, :liquidity_score,
                :slippage_risk, :market_impact_estimate, :liquidity_regime,
                :metadata
            )
        """
        params = {
            "symbol": payload.symbol,
            "timestamp": payload.timestamp,
            "avg_spread_bps": payload.avg_spread_bps,
            "depth_imbalance": payload.depth_imbalance,
            "liquidity_score": payload.liquidity_score,
            "slippage_risk": payload.slippage_risk,
            "market_impact_estimate": payload.market_impact_estimate,
            "liquidity_regime": payload.liquidity_regime,
            "metadata": json.dumps(payload.metadata),
        }
        await self.db._execute_insert(query, params)

    async def _publish(self, payload: LiquidityPayload):
        """Publish liquidity intelligence to Redis."""
        channel = SCOUT_CHANNELS["liquidity_updates"]
        await self._redis.publish(channel, json.dumps(payload.to_dict()))

    async def _publish_summary(self):
        """Publish a compressed summary for Ideator consumption."""
        if self._latest_payload is None:
            return
        summary = scout_summary_for_ideator(liquidity=self._latest_payload)
        await self._redis.set("scout:liquidity_summary", summary, ex=300)

    def get_latest(self) -> Optional[LiquidityPayload]:
        return self._latest_payload
