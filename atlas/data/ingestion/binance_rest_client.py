"""
Binance REST API Polling Client

Replaces the WebSocket approach with REST polling so it works in environments
where Binance WebSocket endpoints are DNS-blocked.

DNS FIX: aiohttp is configured to use Google DNS (8.8.8.8) and Cloudflare DNS
(1.1.1.1) instead of the system resolver, bypassing ISP-level DNS blocks.

Tries multiple Binance base URLs in order:
  api1.binance.com → api2.binance.com → api3.binance.com → api4.binance.com

Polls per symbol:
  • Klines  (1-min OHLCV)  — every 60 s   → L1 bars
  • Depth   (top-20 book)  — every  2 s   → L2 orderbook
  • Trades  (recent fills) — every  5 s   → order_flow  (deduplicated by trade ID)

No authentication required for public market-data endpoints.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Any

import aiohttp
from loguru import logger


# ---------------------------------------------------------------------------
# Fallback base URLs — tried in order until one resolves
# ---------------------------------------------------------------------------
_BASE_URLS = [
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
    "https://api.binance.com",
]

# Alternative public DNS servers — used when system DNS is blocked
_DNS_SERVERS = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]


class BinanceRestClient:
    """
    Polls Binance public REST endpoints and calls async callbacks for each
    data type.

    DNS bypass: uses aiohttp.AsyncResolver(nameservers=_DNS_SERVERS) so
    system DNS blocks don't affect resolution.

    Callback signatures
    -------------------
    trade_handler(data: dict, symbol: str)
        data keys: trade_id, price, qty, buyer_maker, time_ms

    depth_handler(data: dict, symbol: str)
        data keys: bids {price: qty}, asks {price: qty}, last_update_id

    bar_handler(data: dict, symbol: str)
        data keys: open_time_ms, open, high, low, close, volume
    """

    def __init__(
        self,
        trading_pairs: List[str],
        trade_handler: Callable,
        depth_handler: Callable,
        bar_handler: Callable,
        kline_interval: str = "1m",
        poll_trades: float = 5.0,
        poll_depth: float = 2.0,
        poll_bars: float = 60.0,
    ):
        self.trading_pairs = [p.upper() for p in trading_pairs]
        self.trade_handler = trade_handler
        self.depth_handler = depth_handler
        self.bar_handler = bar_handler
        self.kline_interval = kline_interval
        self.poll_trades = poll_trades
        self.poll_depth = poll_depth
        self.poll_bars = poll_bars

        self._stop = asyncio.Event()
        self._session: Optional[aiohttp.ClientSession] = None
        self._base_url: str = _BASE_URLS[0]
        self._last_trade_id: Dict[str, int] = {}   # symbol → last seen trade ID
        self._last_bar_ts:  Dict[str, int] = {}    # symbol → last open_time_ms
        self._tasks: List[asyncio.Task] = []

        # Metrics
        self.trades_written: int = 0
        self.bars_written: int = 0
        self.depth_written: int = 0
        self.errors: int = 0

    # ------------------------------------------------------------------ #
    #  Session creation (with DNS bypass)
    # ------------------------------------------------------------------ #

    def _make_session(self) -> aiohttp.ClientSession:
        """
        Create an aiohttp session that resolves DNS via Google/Cloudflare,
        bypassing any ISP-level DNS blocks on *.binance.com.
        """
        try:
            # aiohttp.AsyncResolver uses aiodns under the hood
            resolver = aiohttp.AsyncResolver(nameservers=_DNS_SERVERS)
            connector = aiohttp.TCPConnector(
                resolver=resolver,
                ssl=True,
                limit=20,
                ttl_dns_cache=300,
            )
            logger.info(f"aiohttp using DNS: {_DNS_SERVERS}")
        except Exception as exc:
            logger.warning(f"AsyncResolver unavailable ({exc}), using system DNS")
            connector = aiohttp.TCPConnector(ssl=True, limit=20, ttl_dns_cache=300)

        return aiohttp.ClientSession(connector=connector)

    # ------------------------------------------------------------------ #
    #  Base URL discovery
    # ------------------------------------------------------------------ #

    async def _resolve_base_url(self) -> str:
        """Try each base URL with a ping; return the first that responds."""
        for url in _BASE_URLS:
            try:
                async with self._session.get(
                    f"{url}/api/v3/ping",
                    timeout=aiohttp.ClientTimeout(total=6),
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✓ Binance REST reachable via: {url}")
                        return url
            except Exception as exc:
                logger.debug(f"  {url} unreachable: {exc}")

        raise ConnectionError(
            "All Binance base URLs are unreachable even with custom DNS. "
            "Check firewall / proxy settings."
        )

    # ------------------------------------------------------------------ #
    #  HTTP helper
    # ------------------------------------------------------------------ #

    async def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET {base_url}{path} and return parsed JSON. Raises on error."""
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientResponseError as exc:
            raise RuntimeError(f"HTTP {exc.status} from {url}: {exc.message}") from exc

    # ------------------------------------------------------------------ #
    #  Per-symbol poll coroutines
    # ------------------------------------------------------------------ #

    async def _poll_trades(self, symbol: str) -> None:
        """
        Poll /api/v3/trades every `poll_trades` seconds.

        NOTE: The public /api/v3/trades endpoint does NOT support fromId.
        fromId is only available on /api/v3/historicalTrades which requires
        an API key. We fetch latest 500 every poll and deduplicate client-side.
        """
        logger.info(f"[trades] starting poll loop for {symbol}")

        while not self._stop.is_set():
            try:
                trades = await self._get(
                    "/api/v3/trades",
                    {"symbol": symbol, "limit": 500},
                )

                last_id = self._last_trade_id.get(symbol)
                new_count = 0

                for t in trades:
                    tid = int(t["id"])
                    if last_id is None or tid > last_id:
                        await self.trade_handler(
                            {
                                "trade_id": tid,
                                "price": float(t["price"]),
                                "qty": float(t["qty"]),
                                "buyer_maker": bool(t["isBuyerMaker"]),
                                "time_ms": int(t["time"]),
                            },
                            symbol,
                        )
                        new_count += 1
                        self.trades_written += 1

                # Update watermark to highest ID seen
                if trades:
                    self._last_trade_id[symbol] = max(int(t["id"]) for t in trades)

                if new_count:
                    logger.debug(
                        f"[trades] {symbol}: +{new_count} new "
                        f"(watermark={self._last_trade_id.get(symbol)})"
                    )

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[trades] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_trades)

    async def _poll_depth(self, symbol: str) -> None:
        """Poll /api/v3/depth every `poll_depth` seconds."""
        logger.info(f"[depth] starting poll loop for {symbol}")

        while not self._stop.is_set():
            try:
                data = await self._get("/api/v3/depth", {"symbol": symbol, "limit": 20})

                bids = {row[0]: float(row[1]) for row in data.get("bids", [])}
                asks = {row[0]: float(row[1]) for row in data.get("asks", [])}

                await self.depth_handler(
                    {
                        "bids": bids,
                        "asks": asks,
                        "last_update_id": int(data.get("lastUpdateId", 0)),
                        "time_ms": int(time.time() * 1000),
                    },
                    symbol,
                )
                self.depth_written += 1

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[depth] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_depth)

    async def _poll_bars(self, symbol: str) -> None:
        """Poll /api/v3/klines every `poll_bars` seconds (deduplicated)."""
        logger.info(f"[bars] starting poll loop for {symbol}")

        while not self._stop.is_set():
            try:
                klines = await self._get(
                    "/api/v3/klines",
                    {"symbol": symbol, "interval": self.kline_interval, "limit": 1},
                )

                if klines:
                    k = klines[0]
                    open_time_ms = int(k[0])

                    if self._last_bar_ts.get(symbol) != open_time_ms:
                        await self.bar_handler(
                            {
                                "open_time_ms": open_time_ms,
                                "open":   float(k[1]),
                                "high":   float(k[2]),
                                "low":    float(k[3]),
                                "close":  float(k[4]),
                                "volume": float(k[5]),
                            },
                            symbol,
                        )
                        self._last_bar_ts[symbol] = open_time_ms
                        self.bars_written += 1
                        logger.debug(f"[bars] {symbol}: new 1m bar written")

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.errors += 1
                logger.warning(f"[bars] {symbol} error: {exc}")

            await asyncio.sleep(self.poll_bars)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Resolve base URL with custom DNS, then spawn one task per symbol × data type."""
        self._stop.clear()

        # Use _make_session() which configures the custom DNS resolver
        self._session = self._make_session()

        try:
            self._base_url = await self._resolve_base_url()
        except ConnectionError:
            await self._session.close()
            raise

        logger.info(
            f"BinanceRestClient starting — "
            f"{len(self.trading_pairs)} pairs, base={self._base_url}"
        )

        for symbol in self.trading_pairs:
            self._tasks.append(asyncio.create_task(self._poll_trades(symbol)))
            self._tasks.append(asyncio.create_task(self._poll_depth(symbol)))
            self._tasks.append(asyncio.create_task(self._poll_bars(symbol)))

        logger.info(f"✓ Spawned {len(self._tasks)} polling tasks")

    async def stop(self) -> None:
        """Cancel all polling tasks and close the HTTP session."""
        logger.info("Stopping BinanceRestClient…")
        self._stop.set()

        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._session and not self._session.closed:
            await self._session.close()

        logger.info(
            f"✓ BinanceRestClient stopped — "
            f"trades={self.trades_written} bars={self.bars_written} "
            f"depth={self.depth_written} errors={self.errors}"
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "base_url": self._base_url,
            "pairs": self.trading_pairs,
            "trades_written": self.trades_written,
            "bars_written": self.bars_written,
            "depth_written": self.depth_written,
            "errors": self.errors,
            "active_tasks": sum(1 for t in self._tasks if not t.done()),
        }
