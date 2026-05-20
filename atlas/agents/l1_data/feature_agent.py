"""
ATLAS Feature Agent v1
Location:
atlas/agents/l1_data/feature_agent.py

Purpose:
- Pull latest Binance market data from TimescaleDB
- Compute Day 2 core feature set
- Write features into `features` table
- Operational Day 2 bridge

Features Included:
- Returns
- Log Returns
- SMA (5/20)
- EMA (12/26)
- RSI (14)
- MACD
- Bollinger Bands
- Rolling Volatility
- VWAP
"""

import asyncio
import math
from datetime import datetime, timezone

import asyncpg
import pandas as pd
import numpy as np
from loguru import logger

from atlas.config.settings import get_settings


class FeatureAgent:
    def __init__(self):
        self.settings = get_settings()
        self.db_pool = None
        self._stop_event = asyncio.Event()
        # Combine both crypto and equity lists
        cp = getattr(self.settings, "crypto_pairs", "").split(",")
        wl = getattr(self.settings, "watchlist", "").split(",")
        self.symbols = list(set(s.strip().upper() for s in cp + wl if s.strip()))

        if not self.symbols:
            self.symbols = ["BTCUSDT", "ETHUSDT", "NVDA", "AAPL", "SPY"]

    # ============================================================
    # DB
    # ============================================================
    async def connect(self):
        if self.db_pool is not None:
            return

        db_url = self.settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        self.db_pool = await asyncpg.create_pool(db_url)
        logger.info("✓ FeatureAgent connected to TimescaleDB")

    async def stop(self):
        self._stop_event.set()
        if self.db_pool is not None:
            await self.db_pool.close()
            self.db_pool = None

    # ============================================================
    # Data Fetch
    # ============================================================
    async def fetch_recent_bars(self, symbol: str, limit: int = 200):
        query = """
            SELECT time AS timestamp, open, high, low, close, volume
            FROM market_data_l1
            WHERE symbol = $1
            ORDER BY time DESC
            LIMIT $2
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, limit)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])

        numeric_cols = ["open", "high", "low", "close", "volume"]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna()

        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"{symbol} dtypes: {df.dtypes.to_dict()}")

        return df

    # ============================================================
    # Feature Computation
    # ============================================================
    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 5:
            return pd.DataFrame()

        df = df.copy()
        df["sma_5"] = df["close"].rolling(5).mean()
        df["ema_5"] = df["close"].ewm(span=5).mean()

        # Returns
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.where(
            (df["close"] > 0) & (df["close"].shift(1) > 0),
            np.log(df["close"] / df["close"].shift(1)),
            np.nan,
        )

        # Trend
        df["sma_5"] = df["close"].rolling(5).mean()
        df["sma_20"] = df["close"].rolling(20).mean()

        df["ema_12"] = df["close"].ewm(span=12).mean()
        df["ema_26"] = df["close"].ewm(span=26).mean()

        # MACD
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9).mean()

        # RSI
        delta = df["close"].diff()

        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()

        rs = gain / loss.replace(0, np.nan)

        df["rsi_14"] = 100 - (100 / (1 + rs))

        # Bollinger
        rolling_mean = df["close"].rolling(20).mean()
        rolling_std = df["close"].rolling(20).std()

        df["bollinger_upper"] = rolling_mean + (2 * rolling_std)
        df["bollinger_lower"] = rolling_mean - (2 * rolling_std)

        # Volatility
        df["rolling_volatility"] = df["returns"].rolling(20).std()

        # VWAP
        typical_price = (df["high"] + df["low"] + df["close"]) / 3

        df["vwap"] = (typical_price * df["volume"]).cumsum() / df[
            "volume"
        ].cumsum().replace(0, np.nan)

        # ── Normalized cross-asset features ──
        vwap = df["vwap"].replace(0, np.nan)
        df["price_vs_vwap_pct"] = np.where(
            vwap.notna(), (df["close"] - vwap) / vwap, np.nan
        )

        denom_26 = df["ema_26"].replace(0, np.nan)
        df["ema_spread_pct"] = np.where(
            denom_26.notna(), (df["ema_12"] - df["ema_26"]) / denom_26, np.nan
        )

        vol_20 = df["volume"].rolling(20).mean().replace(0, np.nan)
        df["relative_volume"] = np.where(vol_20.notna(), df["volume"] / vol_20, np.nan)

        bb_range = (df["bollinger_upper"] - df["bollinger_lower"]).replace(0, np.nan)
        df["bollinger_band_position"] = np.where(
            bb_range.notna(),
            (df["close"] - df["bollinger_lower"]) / bb_range,
            np.nan,
        )

        vol_reg_20 = df["rolling_volatility"].rolling(20).mean().replace(0, np.nan)
        df["volatility_regime"] = np.where(
            vol_reg_20.notna(),
            df["rolling_volatility"] / vol_reg_20,
            np.nan,
        )

        denom_close = df["close"].replace(0, np.nan)
        df["trend_strength"] = np.where(
            denom_close.notna(),
            (df["ema_12"] - df["ema_26"]).abs() / denom_close,
            np.nan,
        )

        # Drop NaNs
        df = df.dropna()

        return df

    # ============================================================
    # Insert — ALL bars, not just latest
    # ============================================================
    async def insert_features(self, symbol: str, df: pd.DataFrame):
        feature_names = [
            "returns",
            "log_returns",
            "sma_5",
            "sma_20",
            "ema_12",
            "ema_26",
            "macd",
            "macd_signal",
            "rsi_14",
            "bollinger_upper",
            "bollinger_lower",
            "rolling_volatility",
            "vwap",
            "price_vs_vwap_pct",
            "ema_spread_pct",
            "relative_volume",
            "bollinger_band_position",
            "volatility_regime",
            "trend_strength",
        ]

        ratio_features = {
            "returns",
            "log_returns",
            "price_vs_vwap_pct",
            "ema_spread_pct",
            "trend_strength",
        }

        records = []
        for _, row in df.iterrows():
            ts = row["timestamp"]
            for name in feature_names:
                val = row.get(name)
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    precision = 8 if name in ratio_features else 6
                    records.append((ts, symbol, name, round(float(val), precision)))

        if not records:
            return

        query = """
            INSERT INTO features (time, symbol, feature_name, value)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
        """

        async with self.db_pool.acquire() as conn:
            for rec in records:
                await conn.execute(query, *rec)

    # ============================================================
    # Symbol Processing
    # ============================================================
    async def process_symbol(self, symbol: str):
        try:
            df = await self.fetch_recent_bars(symbol)

            if df.empty:
                logger.warning(f"No market data for {symbol}")
                return

            feature_df = self.compute_features(df)

            if feature_df.empty:
                logger.warning(f"Not enough data for features: {symbol}")
                return

            generated_keys = [
                c
                for c in feature_df.columns
                if c not in ["timestamp", "open", "high", "low", "close", "volume"]
            ]
            logger.info(f"Generated features for {symbol}: {generated_keys}")

            await self.insert_features(symbol, feature_df)

            logger.info(
                f"✓ Features updated for {symbol}: {len(feature_df)} bars @ "
                f"{feature_df['timestamp'].iloc[-1]}"
            )

        except Exception as e:
            logger.error(f"Feature processing failed for {symbol}: {e}")

    # ============================================================
    # Main Loop
    # ============================================================
    async def run(self):
        await self.connect()

        logger.info(f"✓ FeatureAgent running for symbols: {self.symbols}")

        try:
            while not self._stop_event.is_set():
                cycle_start = datetime.now(timezone.utc)

                logger.info("=== Feature cycle start ===")

                tasks = [self.process_symbol(symbol) for symbol in self.symbols]

                await asyncio.gather(*tasks, return_exceptions=True)

                logger.info("=== Feature cycle complete ===")

                # Align roughly to 60s bars, but remain responsive to stop()
                elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
                sleep_time = max(5, 60 - elapsed)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                except asyncio.TimeoutError:
                    pass
        finally:
            if self.db_pool is not None:
                await self.db_pool.close()
                self.db_pool = None


# ============================================================
# Entry
# ============================================================
async def main():
    logger.info("=== STARTING FEATURE AGENT ===")

    agent = FeatureAgent()

    try:
        await agent.run()

    except KeyboardInterrupt:
        logger.info("FeatureAgent interrupted")

    except Exception as e:
        logger.error(f"FeatureAgent fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
