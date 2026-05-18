"""
Binance REST Polling Agent — L1 Data Ingestion (Crypto)

Replaces WebSocket streaming with REST API polling so it works in
environments where Binance WebSocket endpoints are DNS-blocked.

Data written to TimescaleDB:
  • order_flow       ← trade prints  (every 5 s, deduplicated by trade ID)
  • market_data_l2   ← depth snapshot (every 2 s)
  • market_data_l1   ← 1-min OHLCV bar (every 60 s, dedup by open_time)

Run as a module:
  python -m atlas.agents.l1_data.binance_ws_agent
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from loguru import logger
import redis.asyncio as redis

from atlas.core.agent_base import BaseAgent, AgentLayer, AgentStatus
from atlas.data.storage.timescale_client import (
    TimescaleClient,
    BinanceTradeData,
    BinanceDepthData,
    BarData,
)
from atlas.data.ingestion.binance_rest_client import BinanceRestClient
from atlas.data.ingestion.data_normalizer import _round_ohlcv
from atlas.config.settings import get_settings


class BinanceWebSocketAgent(BaseAgent):
    """
    L1 Data Ingestion Agent for Binance crypto market data.

    Uses REST API polling (not WebSocket) to ingest trade, depth, and
    1-minute bar data into TimescaleDB.
    """

    def __init__(self, redis_client: redis.Redis, db_url: str):
        super().__init__(
            name="BinanceWebSocketAgent",
            agent_type="crypto_data_ingestion",
            layer=AgentLayer.L1,
            redis_client=redis_client,
        )

        self.db_url = db_url
        self.ts_client = TimescaleClient(db_url)
        self.rest_client: Optional[BinanceRestClient] = None

        # Counters
        self._trades_written: int = 0
        self._depth_written: int = 0
        self._bars_written: int = 0
        self._errors: int = 0

        self.settings = get_settings()
        self.trading_pairs: List[str] = self._parse_crypto_pairs()

        logger.info(
            f"BinanceAgent (REST) initialised — "
            f"{len(self.trading_pairs)} pairs: {self.trading_pairs}"
        )

    # ------------------------------------------------------------------ #
    #  Config helpers
    # ------------------------------------------------------------------ #

    def _parse_crypto_pairs(self) -> List[str]:
        """Handle list or comma-string from pydantic-settings."""
        try:
            raw = self.settings.crypto_pairs
            if isinstance(raw, list):
                pairs = [p.strip().upper() for p in raw if str(p).strip()]
            else:
                pairs = [p.strip().upper() for p in str(raw).split(",") if p.strip()]

            if not pairs:
                logger.warning("CRYPTO_PAIRS not set — using defaults")
                return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            return pairs

        except Exception as exc:
            logger.error(f"Error parsing CRYPTO_PAIRS: {exc} — using defaults")
            return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        """Verify DB connection and build the REST client."""
        await self.ts_client.connect()
        logger.info("✓ TimescaleDB connected")

        self.rest_client = BinanceRestClient(
            trading_pairs=self.trading_pairs,
            trade_handler=self._on_trade,
            depth_handler=self._on_depth,
            bar_handler=self._on_bar,
            kline_interval="1m",
            poll_trades=5.0,
            poll_depth=2.0,
            poll_bars=60.0,
        )
        logger.info("✓ BinanceRestClient built")

    async def run(self) -> None:
        """Start REST polling tasks, then monitor them in a health loop."""
        await self.initialize()

        # This resolves the base URL and spawns per-symbol tasks
        await self.rest_client.start()
        logger.info("BinanceAgent REST polling active")

        try:
            tick = 0
            while True:
                await asyncio.sleep(1)
                tick += 1

                # Every 60 s print a status line
                if tick % 60 == 0:
                    await self._log_metrics()

                # Detect complete task death (all tasks done → reconnect)
                status = self.rest_client.get_status()
                if status["active_tasks"] == 0:
                    logger.warning("All REST polling tasks died — restarting client")
                    await self.rest_client.stop()
                    await self.rest_client.start()

        except asyncio.CancelledError:
            logger.info("BinanceAgent run loop cancelled")
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        if self.rest_client:
            await self.rest_client.stop()
        logger.info("BinanceAgent cleanup complete")

    # ------------------------------------------------------------------ #
    #  Data callbacks (called by BinanceRestClient)
    # ------------------------------------------------------------------ #

    async def _on_trade(self, data: Dict[str, Any], symbol: str) -> None:
        """Persist a single trade print to order_flow."""
        try:
            trade = BinanceTradeData(
                time=self._ms_to_dt(data["time_ms"]),
                symbol=symbol,
                price=round(float(data["price"]), 6),
                quantity=round(float(data["qty"]), 6),
                buyer_maker=data["buyer_maker"],
                trade_id=data["trade_id"],
                source="binance",
            )
            await self.ts_client.write_binance_trade(trade)
            self._trades_written += 1

        except Exception as exc:
            self._errors += 1
            logger.error(f"Trade persist error ({symbol}): {exc}")

    async def _on_depth(self, data: Dict[str, Any], symbol: str) -> None:
        """Persist an order-book snapshot to market_data_l2."""
        try:
            depth = BinanceDepthData(
                time=self._ms_to_dt(data["time_ms"]),
                symbol=symbol,
                bids=data["bids"],
                asks=data["asks"],
                source="binance",
                last_update_id=data["last_update_id"],
            )
            await self.ts_client.write_binance_depth(depth)
            self._depth_written += 1

        except Exception as exc:
            self._errors += 1
            logger.error(f"Depth persist error ({symbol}): {exc}")

    async def _on_bar(self, data: Dict[str, Any], symbol: str) -> None:
        """Persist a completed 1-minute OHLCV bar to market_data_l1."""
        try:
            o, h, l, c, v = _round_ohlcv(
                data["open"],
                data["high"],
                data["low"],
                data["close"],
                data["volume"],
                "crypto",
            )
            bar = BarData(
                time=self._ms_to_dt(data["open_time_ms"]),
                symbol=symbol,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
                source="binance",
                interval="1m",
            )
            await self.ts_client.write_bars(symbol, bar)
            self._bars_written += 1
            logger.info(
                f"✓ 1m bar | {symbol} "
                f"O={data['open']} H={data['high']} "
                f"L={data['low']} C={data['close']} "
                f"V={data['volume']:.2f}"
            )

        except Exception as exc:
            self._errors += 1
            logger.error(f"Bar persist error ({symbol}): {exc}")

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ms_to_dt(ts_ms: int) -> datetime:
        try:
            return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    async def _log_metrics(self) -> None:
        try:
            status = self.rest_client.get_status() if self.rest_client else {}
            metrics = {
                "trades_written": self._trades_written,
                "depth_written": self._depth_written,
                "bars_written": self._bars_written,
                "errors": self._errors,
                "active_tasks": str(status.get("active_tasks", 0)),
                "base_url": status.get("base_url", ""),
            }
            key = f"metrics:{self.agent_id}"
            await self._redis.hset(key, mapping={k: str(v) for k, v in metrics.items()})
            await self._redis.expire(key, 300)

            logger.info(
                f"[BinanceAgent] trades={self._trades_written} "
                f"depth={self._depth_written} bars={self._bars_written} "
                f"errors={self._errors} tasks={status.get('active_tasks', 0)}"
            )
        except Exception as exc:
            logger.warning(f"Metrics log error: {exc}")


# --------------------------------------------------------------------------- #
#  Entrypoint
# --------------------------------------------------------------------------- #


async def main():
    settings = get_settings()

    logger.info(f"DB    : {settings.database_url}")
    logger.info(f"Redis : {settings.redis_url}")
    logger.info(f"Pairs : {settings.crypto_pairs}")

    redis_client = await redis.from_url(settings.redis_url)

    agent = BinanceWebSocketAgent(
        redis_client=redis_client,
        db_url=settings.database_url,
    )

    try:
        await agent.start()  # BaseAgent.start() spawns run() as a task
        while True:
            await asyncio.sleep(30)
            logger.debug(f"Agent status: {agent.status}")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    finally:
        await agent.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
