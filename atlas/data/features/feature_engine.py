import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import redis.asyncio as redis
from loguru import logger
from pydantic import BaseModel

from atlas.data.storage.timescale_client import TimescaleClient
from atlas.data.features.technical import compute_technical_features
from atlas.data.features.microstructure import compute_microstructure_features
from atlas.data.features.regime import compute_regime_features


class BarEvent(BaseModel):
    symbol: str
    source: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class FeatureEngine:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas",
    ):
        self.redis_url = redis_url
        self.db_url = db_url
        self.redis_client: Optional[redis.Redis] = None
        self.db_client: Optional[TimescaleClient] = None
        self.running = False

    async def start(self):
        logger.info("Starting Feature Engine...")
        self.redis_client = redis.from_url(self.redis_url)
        self.db_client = TimescaleClient(self.db_url)

        # Test db connection (assuming connect method exists or we just rely on engine)
        try:
            await self.db_client.connect()
            logger.info("Connected to TimescaleDB")
        except Exception as e:
            logger.warning(f"Could not connect to DB initially: {e}")

        self.running = True

        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("market_data")
        logger.info("Subscribed to Redis channel 'market_data'")

        try:
            async for message in pubsub.listen():
                if not self.running:
                    break
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        # Simple check to see if it's a bar event
                        if "open" in data and "close" in data:
                            event = BarEvent(**data)
                            await self.process_bar_event(event)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe("market_data")
            await self.redis_client.close()

    async def stop(self):
        self.running = False
        logger.info("Stopping Feature Engine...")

    async def process_bar_event(self, event: BarEvent):
        start_time = time.time()

        try:
            # 1. Fetch last 200 bars
            end_dt = (
                datetime.utcfromtimestamp(event.timestamp / 1000.0)
                if event.timestamp > 1e10
                else datetime.utcfromtimestamp(event.timestamp)
            )
            start_dt = end_dt - timedelta(
                days=5
            )  # Retrieve some history to get 200 bars, usually enough for 1m timeframe

            df = await self.db_client.get_bars(
                symbol=event.symbol, start=start_dt, end=end_dt, interval="1m"
            )

            # If DB is empty, use current bar as a 1-row df just to avoid crash, but technicals will be None
            if df is None or df.empty:
                import pandas as pd

                df = pd.DataFrame(
                    [
                        {
                            "time": end_dt,
                            "symbol": event.symbol,
                            "open": event.open,
                            "high": event.high,
                            "low": event.low,
                            "close": event.close,
                            "volume": event.volume,
                        }
                    ]
                )
            else:
                # Keep only last 200 rows
                df = df.tail(200).copy()

            # 2. Call technical.py
            tech_features = compute_technical_features(df)

            # 3. Call microstructure.py
            # Since we only get bar events, we pass empty lists for order book.
            # In a real scenario, we might query redis for the latest orderbook snapshot.
            bids = []
            asks = []
            micro_features = compute_microstructure_features(
                bids, asks, recent_trades=None
            )

            # 4. Compute normalized cross-asset features on the DataFrame
            import pandas as _pd
            import numpy as _np

            _df = df.copy()
            _df["ema_12"] = _df["close"].ewm(span=12).mean()
            _df["ema_26"] = _df["close"].ewm(span=26).mean()
            _df["rolling_volatility"] = _df["close"].pct_change().rolling(20).std()
            rolling_mean_20 = _df["close"].rolling(20).mean()
            rolling_std_20 = _df["close"].rolling(20).std()
            _df["bollinger_upper"] = rolling_mean_20 + 2 * rolling_std_20
            _df["bollinger_lower"] = rolling_mean_20 - 2 * rolling_std_20
            tp = (_df["high"] + _df["low"] + _df["close"]) / 3
            _df["vwap"] = (tp * _df["volume"]).cumsum() / _df[
                "volume"
            ].cumsum().replace(0, _np.nan)
            vol_20 = _df["volume"].rolling(20).mean().replace(0, _np.nan)
            _df["relative_volume"] = _df["volume"] / vol_20
            vol_reg_20 = (
                _df["rolling_volatility"].rolling(20).mean().replace(0, _np.nan)
            )
            _df["volatility_regime"] = _df["rolling_volatility"] / vol_reg_20
            _df = _df.replace([_np.inf, -_np.inf], _np.nan).dropna()

            if not _df.empty:
                last = _df.iloc[-1]
                for key in (
                    "ema_12",
                    "ema_26",
                    "bollinger_upper",
                    "bollinger_lower",
                    "vwap",
                    "rolling_volatility",
                    "relative_volume",
                    "volatility_regime",
                ):
                    tech_features[key] = (
                        float(last.get(key, _np.nan))
                        if key not in tech_features
                        else tech_features[key]
                    )
                vwap = last.get("vwap", _np.nan)
                close_val = last.get("close", _np.nan)
                ema_12_v = last.get("ema_12", _np.nan)
                ema_26_v = last.get("ema_26", _np.nan)
                bb_low = last.get("bollinger_lower", _np.nan)
                bb_high = last.get("bollinger_upper", _np.nan)
                if _pd.notna(vwap) and vwap != 0:
                    tech_features["price_vs_vwap_pct"] = (close_val - vwap) / vwap
                if _pd.notna(ema_26_v) and ema_26_v != 0:
                    tech_features["ema_spread_pct"] = (ema_12_v - ema_26_v) / ema_26_v
                if _pd.notna(bb_low) and _pd.notna(bb_high) and (bb_high - bb_low) != 0:
                    tech_features["bollinger_band_position"] = (close_val - bb_low) / (
                        bb_high - bb_low
                    )
                if _pd.notna(close_val) and close_val != 0:
                    tech_features["trend_strength"] = (
                        abs(ema_12_v - ema_26_v) / close_val
                    )

            # 5. Call regime.py
            regime_features = compute_regime_features(
                tech_features, current_time=end_dt
            )

            # 6. Merge all into one features dict
            all_features = {}
            for k, v in tech_features.items():
                if v is not None:
                    all_features[k] = float(v)
            for k, v in micro_features.items():
                if v is not None:
                    all_features[k] = float(v)

            # We don't store regime strings in Timescale normally as numeric features,
            # but we can send them to Redis

            # 6. Feature-aware precision rounding + NaN/inf guard
            def _precision(name: str, value: float) -> float:
                """Apply feature-appropriate decimal precision."""
                if name in ("returns", "log_returns"):
                    return round(value, 8)  # tiny values need more places
                if name.startswith("rsi_"):
                    return round(value, 4)  # RSI 0–100, 4dp is plenty
                if name in (
                    "price_vs_vwap_pct",
                    "ema_spread_pct",
                    "trend_strength",
                ):
                    return round(value, 8)  # % ratios, keep 8dp
                return round(value, 6)  # default: 6dp

            import math

            rounded = {}
            for k, v in all_features.items():
                try:
                    fv = float(v)
                    if math.isnan(fv) or math.isinf(fv):
                        continue  # silently drop bad values
                    rounded[k] = _precision(k, fv)
                except (TypeError, ValueError):
                    continue
            all_features = rounded

            # 7. Write all features to TimescaleDB
            if all_features:
                await self.db_client.write_features(
                    symbol=event.symbol, features_dict=all_features
                )

            # 8. Publish to Redis "strategy_signals"
            signal_payload = {
                "symbol": event.symbol,
                "timestamp": event.timestamp,
                "feature_count": len(all_features),
                "regime": regime_features,
            }
            await self.redis_client.publish(
                "strategy_signals", json.dumps(signal_payload)
            )

            # 9. Log elapsed time
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Computed {len(all_features)} features for {event.symbol} in {elapsed_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Failed to process bar event for {event.symbol}: {e}")


if __name__ == "__main__":
    engine = FeatureEngine()
    asyncio.run(engine.start())
