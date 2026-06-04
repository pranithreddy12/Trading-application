"""
Polygon.io REST API Polling Client

Polls Polygon REST endpoints for 1-minute bars, trades, and snapshot quotes.
Alternative to the WebSocket client for environments where WebSocket is blocked.

Rate limiting (free tier: 5 req/min, paid: much higher):
  Uses a token-bucket rate limiter. Configure `calls_per_minute` based on tier.

Endpoints:
  * /v2/aggs/ticker/{symbol}/range/1/minute  → 1-min OHLCV bars
  * /v3/trades/{symbol}                        → recent trades (dedup by ID)
  * /v2/snapshot/loc/us/markets/stocks/tickers → current quote snapshot

Callback signatures:
  bar_handler(data: dict, symbol: str)
    data keys: symbol, time, open, high, low, close, volume, vwap
  trade_handler(data: dict, symbol: str)
    data keys: trade_id, price, size, time_ms, conditions
  snapshot_handler(data: dict, symbol: str)
    data keys: bid_price, ask_price, bid_size, ask_size, last_price, volume
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, List, Optional, Any

import aiohttp
from loguru import logger

# Fallback DNS servers — used when system DNS blocks polygon.io
_DNS_SERVERS = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]


class _TokenBucket:
    """Simple token-bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    async def acquire(self) -> None:
        while self.tokens < 1.0:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens < 1.0:
                await asyncio.sleep(0.1)
        self.tokens -= 1.0
        self.last_refill = time.monotonic()


class PolygonRestClient:
    """
    Polls Polygon REST endpoints and calls async callbacks for each data type.

    Usage:
        client = PolygonRestClient(api_key, symbols, bar_handler=..., ...)
        await client.start()
        # ... run forever ...
        await client.stop()
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        api_key: str,
        symbols: List[str],
        bar_handler: Callable,
        trade_handler: Optional[Callable] = None,
        snapshot_handler: Optional[Callable] = None,
        poll_bars: float = 60.0,
        poll_trades: float = 10.0,
        poll_snapshot: float = 10.0,
        calls_per_minute: int = 5,
        fallback_fetch: Optional[Callable] = None,
    ):
        self.api_key = api_key
        self.symbols = symbols
        self.bar_handler = bar_handler
        self.trade_handler = trade_handler
        self.snapshot_handler = snapshot_handler
        self.poll_bars = poll_bars
        self.poll_trades = poll_trades
        self.poll_snapshot = poll_snapshot

        rate = calls_per_minute / 60.0
        self._limiter = _TokenBucket(rate=rate, capacity=calls_per_minute)

        self._stop = asyncio.Event()
        self._session: Optional[aiohttp.ClientSession] = None
        self._tasks: List[asyncio.Task] = []

        # Dedup watermarks
        self._last_bar_time: Dict[str, int] = {}
        self._last_trade_id: Dict[str, int] = {}

        # Optional async callable fallback_fetch(symbol, start_dt, end_dt) -> list[dict]
        self._fallback_fetch = fallback_fetch

        # Metrics
        self.bars_written: int = 0
        self.trades_written: int = 0
        self.snapshots_written: int = 0
        self.errors: int = 0

    # ------------------------------------------------------------------ #
    #  Session creation (with DNS bypass — same pattern as BinanceRestClient)
    # ------------------------------------------------------------------ #

    def _make_session(self) -> aiohttp.ClientSession:
        try:
            resolver = aiohttp.AsyncResolver(nameservers=_DNS_SERVERS)
            connector = aiohttp.TCPConnector(
                resolver=resolver, ssl=True, limit=20, ttl_dns_cache=300
            )
            logger.info(f"Polygon DNS via: {_DNS_SERVERS}")
        except Exception as exc:
            logger.warning(f"AsyncResolver unavailable ({exc}), using system DNS")
            connector = aiohttp.TCPConnector(ssl=True, limit=20, ttl_dns_cache=300)
        return aiohttp.ClientSession(connector=connector)

    # ------------------------------------------------------------------ #
    #  HTTP helper
    # ------------------------------------------------------------------ #

    async def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        await self._limiter.acquire()
        url = f"{self.BASE_URL}{path}"
        req_params = dict(params or {})
        req_params["apiKey"] = self.api_key
        try:
            async with self._session.get(
                url,
                params=req_params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientResponseError as exc:
            raise RuntimeError(f"HTTP {exc.status} from {url}: {exc.message}") from exc

    # ------------------------------------------------------------------ #
    #  Poll coroutines
    # ------------------------------------------------------------------ #

    async def _poll_bars(self, symbol: str) -> None:
        """Poll /v2/aggs/ticker/{symbol}/range/1/minute — dedup by timestamp."""
        logger.info(f"[bars] starting poll loop for {symbol}")
        while not self._stop.is_set():
            try:
                now = datetime.now(timezone.utc)
                start_dt = now - timedelta(days=2)
                data = await self._get(
                    f"/v2/aggs/ticker/{symbol}/range/1/minute/"
                    f"{start_dt.strftime('%Y-%m-%d')}/"
                    f"{now.strftime('%Y-%m-%d')}",
                    {"adjusted": "true", "sort": "asc", "limit": 5000},
                )

                # Polygon can return top-level status 'DELAYED' for free-tier keys
                results = data.get("results", [])
                status = data.get("status")

                # If Polygon is delayed or returned no results, attempt fallback if provided
                if (status == "DELAYED" or not results) and self._fallback_fetch:
                    try:
                        logger.info(f"[bars] {symbol} — Polygon delayed/empty, invoking fallback fetch")
                        fb = await self._fallback_fetch(symbol, start_dt, now)
                        if fb:
                            results = fb
                    except Exception as exc:
                        logger.warning(f"[bars] fallback fetch error for {symbol}: {exc}")
                new_count = 0
                last_ts = self._last_bar_time.get(symbol, 0)
                for bar in results:
                    ts = int(bar["t"])
                    if ts > last_ts:
                        await self.bar_handler(
                            {
                                "symbol": symbol,
                                "time": ts,
                                "open": float(bar.get("o", 0)),
                                "high": float(bar.get("h", 0)),
                                "low": float(bar.get("l", 0)),
                                "close": float(bar.get("c", 0)),
                                "volume": float(bar.get("v", 0)),
                                "vwap": float(bar.get("vw", 0)),
                            },
                            symbol,
                        )
                        new_count += 1
                        self.bars_written += 1

                if results:
                    # Ensure timestamp field accessibility regardless of source
                    self._last_bar_time[symbol] = max(int(r["t"]) for r in results)

                if new_count:
                    logger.debug(f"[bars] {symbol}: +{new_count} new bars")

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[bars] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_bars)

    async def _poll_trades(self, symbol: str) -> None:
        """Poll /v3/trades/{symbol} — dedup by trade_id."""
        logger.info(f"[trades] starting poll loop for {symbol}")
        while not self._stop.is_set():
            try:
                data = await self._get(
                    f"/v3/trades/{symbol}",
                    {"limit": 500},
                )
                results = data.get("results", [])
                last_id = self._last_trade_id.get(symbol)
                new_count = 0
                for t in results:
                    ts_ns = int(t.get("participant_timestamp", 0))
                    tid = t.get("id", str(ts_ns))
                    if last_id is None or tid > last_id:
                        await self.trade_handler(
                            {
                                "trade_id": tid,
                                "price": float(t.get("price", 0)),
                                "size": float(t.get("size", 0)),
                                "time_ns": ts_ns,
                                "conditions": t.get("conditions", []),
                            },
                            symbol,
                        )
                        new_count += 1
                        self.trades_written += 1

                if results:
                    self._last_trade_id[symbol] = max(
                        r.get("id", str(r.get("participant_timestamp", 0)))
                        for r in results
                    )

                if new_count:
                    logger.debug(f"[trades] {symbol}: +{new_count} new")

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[trades] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_trades)

    async def _poll_snapshot(self, symbol: str) -> None:
        """
        Poll /v2/snapshot/loc/us/markets/stocks/tickers/{symbol}.

        Provides current bid/ask, last trade price, and daily volume.
        """
        logger.info(f"[snapshot] starting poll loop for {symbol}")
        while not self._stop.is_set():
            try:
                data = await self._get(
                    f"/v2/snapshot/loc/us/markets/stocks/tickers/{symbol}",
                )
                ticker = data.get("ticker", {})
                session = ticker.get("session", {})
                last_trade = ticker.get("lastTrade", {}) or {}
                await self.snapshot_handler(
                    {
                        "bid_price": float(ticker.get("bidPrice", 0)),
                        "ask_price": float(ticker.get("askPrice", 0)),
                        "bid_size": float(ticker.get("bidSize", 0)),
                        "ask_size": float(ticker.get("askSize", 0)),
                        "last_price": float(
                            last_trade.get("p", session.get("close", 0))
                        ),
                        "volume": float(session.get("volume", 0)),
                        "time_ms": int(time.time() * 1000),
                    },
                    symbol,
                )
                self.snapshots_written += 1

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[snapshot] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_snapshot)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        self._stop.clear()
        self._session = self._make_session()

        logger.info(
            f"PolygonRestClient starting — {len(self.symbols)} symbols, "
            f"rate={self._limiter.rate * 60:.0f} req/min"
        )

        for symbol in self.symbols:
            self._tasks.append(asyncio.create_task(self._poll_bars(symbol)))
            if self.trade_handler:
                self._tasks.append(asyncio.create_task(self._poll_trades(symbol)))
            if self.snapshot_handler:
                self._tasks.append(asyncio.create_task(self._poll_snapshot(symbol)))

        logger.info(f"Started {len(self._tasks)} polling tasks")

    async def stop(self) -> None:
        logger.info("Stopping PolygonRestClient…")
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info(
            f"Stopped — bars={self.bars_written} trades={self.trades_written} "
            f"snapshots={self.snapshots_written} errors={self.errors}"
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "symbols": self.symbols,
            "bars_written": self.bars_written,
            "trades_written": self.trades_written,
            "snapshots_written": self.snapshots_written,
            "errors": self.errors,
            "active_tasks": sum(1 for t in self._tasks if not t.done()),
        }
