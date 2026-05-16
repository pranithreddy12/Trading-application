"""
Polygon.io WebSocket Agent — L1 Data Ingestion (Equities)

Receives Q (Quote), T (Trade), A (Aggregate/1-min bar) events from Polygon,
maps them to TimescaleDB models, and persists via TimescaleClient.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from loguru import logger
import redis.asyncio as redis

from atlas.core.agent_base import BaseAgent, AgentLayer, AgentStatus
from atlas.data.storage.timescale_client import (
    TimescaleClient,
    QuoteData,
    TradeData,
    AggregateData,
)
from atlas.data.ingestion.polygon_ws_client import PolygonWebSocketClient
from atlas.data.ingestion.data_normalizer import (
    _round_ohlcv,
    _round_orderbook,
    _round_trade,
)
from atlas.config.settings import get_settings


class PolygonWebSocketAgent(BaseAgent):
    """
    L1 Data Ingestion Agent for Polygon.io real-time equities data.

    Subscribes to Q.*, T.*, A.* streams for every symbol in WATCHLIST.
    Writes to TimescaleDB: market_data_l2 (quotes), order_flow (trades),
    and market_data_l1 (1-min aggregates).
    """

    def __init__(self, redis_client: redis.Redis, db_url: str):
        super().__init__(
            name="PolygonWebSocketAgent",
            agent_type="equity_data_ingestion",
            layer=AgentLayer.L1,
            redis_client=redis_client,
        )

        self.db_url = db_url
        self.ts_client = TimescaleClient(db_url)
        self.ws_client: Optional[PolygonWebSocketClient] = None

        # Counters
        self._messages_received: int = 0
        self._messages_processed: int = 0
        self._messages_failed: int = 0
        self._db_errors: int = 0

        self.settings = get_settings()
        self.symbols: List[str] = self._parse_watchlist()

        logger.info(
            f"PolygonWebSocketAgent initialised — "
            f"{len(self.symbols)} symbols: {self.symbols}"
        )

    # ------------------------------------------------------------------ #
    #  Config helpers
    # ------------------------------------------------------------------ #

    def _parse_watchlist(self) -> List[str]:
        """Return watchlist as a flat list; handles list or comma-string."""
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
        """Verify DB connection and build the WebSocket client."""
        await self.ts_client.connect()
        logger.info("✓ TimescaleDB connected")

        self.ws_client = PolygonWebSocketClient(
            api_key=self.settings.polygon_api_key,
            symbols=self.symbols,
            message_handler=self._handle_message,
            stream_types=["Q", "T", "A"],
            delayed=getattr(self.settings, "polygon_delayed", True),
        )
        logger.info("✓ PolygonWebSocketClient initialised")

    async def run(self) -> None:
        """
        Main run loop.

        Starts the WS client as a background task, then monitors it.
        If the task dies unexpectedly the run() method raises, which
        triggers BaseAgent's retry-with-backoff logic.
        """
        await self.initialize()

        await self.ws_client.start()
        logger.info("PolygonWebSocketAgent run loop active")

        try:
            metrics_tick = 0
            while True:
                await asyncio.sleep(1)
                metrics_tick += 1

                # Detect a crashed WS task and propagate the error
                if (
                    self.ws_client._task
                    and self.ws_client._task.done()
                    and not self.ws_client._task.cancelled()
                ):
                    exc = self.ws_client._task.exception()
                    if exc:
                        raise RuntimeError(f"WS task died: {exc}") from exc

                if metrics_tick % 60 == 0:
                    await self._log_metrics()

        except asyncio.CancelledError:
            logger.info("PolygonWebSocketAgent run loop cancelled")
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        if self.ws_client:
            await self.ws_client.stop()
        logger.info("PolygonWebSocketAgent cleanup complete")

    # ------------------------------------------------------------------ #
    #  Message handlers
    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Route an incoming Polygon frame to the correct handler."""
        self._messages_received += 1

        try:
            ev = message.get("ev")

            if ev == "Q":
                await self._handle_quote(message)
            elif ev == "T":
                await self._handle_trade(message)
            elif ev == "A":
                await self._handle_aggregate(message)
            else:
                logger.debug(f"Unhandled ev={ev!r}")
                return

            self._messages_processed += 1

        except Exception as exc:
            self._messages_failed += 1
            logger.error(f"Message processing error (ev={message.get('ev')}): {exc}")

    async def _handle_quote(self, msg: Dict[str, Any]) -> None:
        """
        Polygon Q event → market_data_l2 (quote snapshot).

        Key fields:
            sym  = symbol
            t    = SIP timestamp (ms)
            bp   = bid price
            ap   = ask price
            bs   = bid size
            as_  = ask size  (note: 'as' is a Python keyword → 'as' key)
            bx   = bid exchange
            ax   = ask exchange
        """
        try:
            bp, ap, bs, asz = _round_orderbook(
                msg.get("bp", 0.0),
                msg.get("ap", 0.0),
                msg.get("bs", 0.0),
                msg.get("as", 0.0),
            )
            quote = QuoteData(
                time=self._ms_to_dt(msg.get("t")),
                symbol=msg.get("sym", ""),
                bid=bp,
                ask=ap,
                bid_size=bs,
                ask_size=asz,
                bid_exchange=str(msg.get("bx", "")),
                ask_exchange=str(msg.get("ax", "")),
                source="polygon",
            )
            await self.ts_client.write_quote(quote)

        except Exception as exc:
            self._db_errors += 1
            logger.error(f"Quote persist error ({msg.get('sym')}): {exc}")
            raise

    async def _handle_trade(self, msg: Dict[str, Any]) -> None:
        """
        Polygon T event → order_flow.

        Key fields:
            sym  = symbol
            t    = SIP timestamp (ms)
            p    = price
            s    = size
            x    = exchange ID
        """
        try:
            price, size = _round_trade(
                msg.get("p", 0.0),
                msg.get("s", 0.0),
            )
            trade = TradeData(
                time=self._ms_to_dt(msg.get("t")),
                symbol=msg.get("sym", ""),
                price=price,
                size=size,
                side="unknown",
                exchange=str(msg.get("x", "")),
                source="polygon",
            )
            await self.ts_client.write_trade(trade)

        except Exception as exc:
            self._db_errors += 1
            logger.error(f"Trade persist error ({msg.get('sym')}): {exc}")
            raise

    async def _handle_aggregate(self, msg: Dict[str, Any]) -> None:
        """
        Polygon A event → market_data_l1 (1-min OHLCV bar).

        Key fields:
            sym  = symbol
            t    = tick start timestamp (ms)
            o/h/l/c/v/vw = OHLCV + VWAP
        """
        try:
            o, h, l, c, v = _round_ohlcv(
                msg.get("o", 0.0),
                msg.get("h", 0.0),
                msg.get("l", 0.0),
                msg.get("c", 0.0),
                msg.get("v", 0.0),
                "equity",
            )
            agg = AggregateData(
                time=self._ms_to_dt(msg.get("t")),
                symbol=msg.get("sym", ""),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
                vwap=round(float(msg.get("vw", 0.0)), 6),
                source="polygon",
                interval="1m",
            )
            await self.ts_client.write_aggregate(agg)

        except Exception as exc:
            self._db_errors += 1
            logger.error(f"Aggregate persist error ({msg.get('sym')}): {exc}")
            raise

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ms_to_dt(ts_ms: Optional[int]) -> datetime:
        """Convert Polygon millisecond timestamp to UTC datetime."""
        if not ts_ms:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    async def _log_metrics(self) -> None:
        """Push agent metrics to Redis (TTL 5 min)."""
        try:
            ws_status = self.ws_client.get_status() if self.ws_client else {}
            metrics = {
                "messages_received": self._messages_received,
                "messages_processed": self._messages_processed,
                "messages_failed": self._messages_failed,
                "db_errors": self._db_errors,
                "connected": str(ws_status.get("connected", False)),
                "authenticated": str(ws_status.get("authenticated", False)),
                "symbols": len(ws_status.get("subscribed_symbols", [])),
            }

            key = f"metrics:{self.agent_id}"
            await self._redis.hset(key, mapping={k: str(v) for k, v in metrics.items()})
            await self._redis.expire(key, 300)

            logger.info(
                f"[PolygonAgent] rx={self._messages_received} "
                f"ok={self._messages_processed} "
                f"err={self._messages_failed} "
                f"db_err={self._db_errors} "
                f"auth={ws_status.get('authenticated', False)}"
            )
        except Exception as exc:
            logger.warning(f"Metrics log error: {exc}")


# --------------------------------------------------------------------------- #
#  Entrypoint
# --------------------------------------------------------------------------- #


async def main():
    settings = get_settings()

    logger.info(f"DB URL  : {settings.database_url}")
    logger.info(f"Redis   : {settings.redis_url}")
    logger.info(f"Polygon key present: {bool(settings.polygon_api_key)}")

    redis_client = await redis.from_url(settings.redis_url)

    agent = PolygonWebSocketAgent(
        redis_client=redis_client,
        db_url=settings.database_url,
    )

    try:
        await agent.start()  # BaseAgent.start() creates the run task
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
