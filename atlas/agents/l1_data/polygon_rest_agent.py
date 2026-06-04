"""
Polygon REST Polling Agent — L1 Data Ingestion (Equities)

Alternative to the WebSocket agent for environments where WebSocket is
unreliable or blocked. Uses Polygon REST API polling for bars, trades,
and snapshot quotes.

Data written to TimescaleDB:
  * market_data_l1  ← 1-min OHLCV bars (every 60 s, dedup by timestamp)
  * order_flow      ← trade prints (every 10 s, dedup by trade ID)
  * market_data_l2  ← quote snapshot (every 10 s, best bid/ask)

Run:
  python -m atlas.agents.l1_data.polygon_rest_agent
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from loguru import logger
import redis.asyncio as redis

from atlas.core.agent_base import BaseAgent, AgentLayer
from atlas.data.storage.timescale_client import (
    TimescaleClient,
    BarData,
    TradeData,
    QuoteData,
)
from atlas.data.ingestion.data_normalizer import (
    _round_ohlcv,
    _round_orderbook,
    _round_trade,
)
from atlas.data.ingestion.polygon_rest_client import PolygonRestClient
from atlas.config.settings import get_settings


class PolygonRestAgent(BaseAgent):
    """
    L1 Data Ingestion Agent for Polygon.io equities via REST polling.

    Uses Polygon REST endpoints (not WebSocket) to fetch 1-min bars,
    recent trades, and quote snapshots. Writes to TimescaleDB.
    """

    def __init__(self, redis_client: redis.Redis, db_url: str):
        super().__init__(
            name="PolygonRestAgent",
            agent_type="equity_data_ingestion",
            layer=AgentLayer.L1,
            redis_client=redis_client,
        )

        self.db_url = db_url
        self.ts_client = TimescaleClient(db_url)
        self.rest_client: Optional[PolygonRestClient] = None

        self._bars_written: int = 0
        self._trades_written: int = 0
        self._quotes_written: int = 0
        self._errors: int = 0

        self.settings = get_settings()
        self.symbols: List[str] = self._parse_watchlist()

        logger.info(
            f"PolygonRestAgent initialised — "
            f"{len(self.symbols)} symbols: {self.symbols}"
        )

    def _parse_watchlist(self) -> List[str]:
        try:
            raw = self.settings.watchlist
            if isinstance(raw, list):
                syms = [s.strip().upper() for s in raw if s.strip()]
            else:
                syms = [s.strip().upper() for s in str(raw).split(",") if s.strip()]
            if not syms:
                logger.warning("Empty watchlist — using defaults")
                return ["AAPL", "MSFT", "GOOGL"]
            return syms
        except Exception as exc:
            logger.error(f"Error parsing watchlist: {exc} — using defaults")
            return ["AAPL", "MSFT", "GOOGL"]

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        await self.ts_client.connect()
        logger.info("TimescaleDB connected")

        delayed = getattr(self.settings, "polygon_delayed", True)
        calls_per_minute = 5 if delayed else 60

        snapshot_handler = self._on_snapshot if not delayed else None
        if delayed:
            logger.warning(
                "Polygon free/delayed tier: snapshot endpoint unavailable "
                "(requires paid subscription). Bars + trades only."
            )

        # Optional fallback to yfinance when Polygon is delayed/no-data
        fallback_fetch = None
        try:
            if getattr(self.settings, "polygon_fallback_yfinance", False):
                from atlas.data.ingestion.yfinance_client import fetch_1m_bars

                fallback_fetch = fetch_1m_bars
                logger.info("Polygon fallback to yfinance enabled")
        except Exception as exc:
            logger.warning(f"Could not enable yfinance fallback: {exc}")

        self.rest_client = PolygonRestClient(
            api_key=self.settings.polygon_api_key,
            symbols=self.symbols,
            bar_handler=self._on_bar,
            trade_handler=self._on_trade,
            snapshot_handler=snapshot_handler,
            poll_bars=60.0,
            poll_trades=10.0,
            poll_snapshot=10.0,
            calls_per_minute=calls_per_minute,
            fallback_fetch=fallback_fetch,
        )
        logger.info("PolygonRestClient built")

    async def run(self) -> None:
        await self.initialize()
        await self.rest_client.start()
        logger.info("PolygonRestAgent REST polling active")

        try:
            tick = 0
            while True:
                await asyncio.sleep(1)
                tick += 1

                if tick % 60 == 0:
                    await self._log_metrics()

                status = self.rest_client.get_status()
                if status["active_tasks"] == 0:
                    logger.warning("All REST polling tasks died — restarting")
                    await self.rest_client.stop()
                    await self.rest_client.start()

        except asyncio.CancelledError:
            logger.info("PolygonRestAgent run loop cancelled")
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        if self.rest_client:
            await self.rest_client.stop()
        logger.info("PolygonRestAgent cleanup complete")

    # ------------------------------------------------------------------ #
    #  Data callbacks (called by PolygonRestClient)
    # ------------------------------------------------------------------ #

    async def _on_bar(self, data: Dict[str, Any], symbol: str) -> None:
        o, h, l, c, v = _round_ohlcv(
            data["open"],
            data["high"],
            data["low"],
            data["close"],
            data["volume"],
            "equity",
        )
        bar = BarData(
            time=datetime.fromtimestamp(data["time"] / 1000, tz=timezone.utc),
            symbol=symbol,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
            source="polygon",
            interval="1m",
            asset_class="equity",
        )
        try:
            await self.ts_client.write_bars(symbol, bar)
            self._bars_written += 1
            logger.debug(f"1m bar | {symbol} O={data['open']} C={data['close']}")
        except Exception as exc:
            self._errors += 1
            logger.error(f"Bar persist error ({symbol}): {exc}")
            # Propagate to the poller so it doesn't advance the dedup watermark
            raise

    async def _on_trade(self, data: Dict[str, Any], symbol: str) -> None:
        price, size = _round_trade(data["price"], data["size"])
        trade = TradeData(
            time=datetime.fromtimestamp(
                data["time_ns"] / 1_000_000_000, tz=timezone.utc
            ),
            symbol=symbol,
            price=price,
            size=size,
            side="unknown",
            exchange="polygon",
            source="polygon",
        )
        try:
            await self.ts_client.write_trade(trade)
            self._trades_written += 1
        except Exception as exc:
            self._errors += 1
            logger.error(f"Trade persist error ({symbol}): {exc}")
            raise

    async def _on_snapshot(self, data: Dict[str, Any], symbol: str) -> None:
        bp, ap, bs, asz = _round_orderbook(
            data["bid_price"],
            data["ask_price"],
            data["bid_size"],
            data["ask_size"],
        )
        quote = QuoteData(
            time=datetime.fromtimestamp(data["time_ms"] / 1000, tz=timezone.utc),
            symbol=symbol,
            bid=bp,
            ask=ap,
            bid_size=bs,
            ask_size=asz,
            bid_exchange="",
            ask_exchange="",
            source="polygon",
        )
        try:
            await self.ts_client.write_quote(quote)
            self._quotes_written += 1
        except Exception as exc:
            self._errors += 1
            logger.error(f"Quote persist error ({symbol}): {exc}")
            raise

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    async def _log_metrics(self) -> None:
        try:
            status = self.rest_client.get_status() if self.rest_client else {}
            metrics = {
                "bars_written": str(self._bars_written),
                "trades_written": str(self._trades_written),
                "quotes_written": str(self._quotes_written),
                "errors": str(self._errors),
                "active_tasks": str(status.get("active_tasks", 0)),
            }
            key = f"metrics:{self.agent_id}"
            await self._redis.hset(key, mapping=metrics)
            await self._redis.expire(key, 300)
            logger.info(
                f"[PolygonRestAgent] bars={self._bars_written} "
                f"trades={self._trades_written} quotes={self._quotes_written} "
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
    logger.info(f"Polygon key present: {bool(settings.polygon_api_key)}")

    redis_client = await redis.from_url(settings.redis_url)

    agent = PolygonRestAgent(
        redis_client=redis_client,
        db_url=settings.database_url,
    )

    try:
        await agent.start()
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
