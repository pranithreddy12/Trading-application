"""
Binance WebSocket Client using the official python-binance library.

Uses AsyncClient + BinanceSocketManager.multiplex_socket() for production-grade
connection management with automatic reconnection and clean shutdown.

Streams subscribed per pair:
  - {symbol}@trade          — individual trade prints
  - {symbol}@depth20@100ms  — top-20 order book, refreshed every 100 ms
"""

import asyncio
from typing import Callable, Dict, List, Optional, Any
from loguru import logger

from binance import AsyncClient, BinanceSocketManager


class BinanceWebSocketClient:
    """
    Production Binance WebSocket client built on top of python-binance.

    python-binance handles:
      - SSL / keepalive
      - Automatic reconnection inside multiplex_socket()
      - Stream name formatting

    This wrapper adds:
      - Configurable pair + stream-type lists
      - Exponential backoff between top-level reconnect attempts
      - Clean asyncio task lifecycle
    """

    BASE_BACKOFF: int = 2    # seconds
    MAX_BACKOFF: int = 60    # seconds

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        trading_pairs: List[str],
        message_handler: Callable,
        stream_types: Optional[List[str]] = None,
    ):
        """
        Args:
            api_key:        Binance API key (public)
            api_secret:     Binance API secret
            trading_pairs:  e.g. ['BTCUSDT', 'ETHUSDT']
            message_handler: async callable(data: dict, stream_name: str)
            stream_types:   e.g. ['trade', 'depth20@100ms']
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.trading_pairs = [p.lower() for p in trading_pairs]
        self.message_handler = message_handler
        self.stream_types = stream_types or ["trade", "depth20@100ms"]

        self.is_connected: bool = False
        self._stop_event = asyncio.Event()
        self._reconnect_delay: int = self.BASE_BACKOFF
        self._client: Optional[AsyncClient] = None
        self._task: Optional[asyncio.Task] = None

        logger.info(
            f"BinanceWebSocketClient ready — "
            f"pairs={self.trading_pairs}, streams={self.stream_types}"
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _build_streams(self) -> List[str]:
        """Build the list of stream names for multiplex_socket()."""
        return [
            f"{pair}@{stype}"
            for pair in self.trading_pairs
            for stype in self.stream_types
        ]

    async def _connect_loop(self) -> None:
        """Outer reconnect loop — runs until _stop_event is set."""
        logger.info("Binance WebSocket connect loop starting…")

        while not self._stop_event.is_set():
            try:
                await self._run_session()
                # _run_session only returns cleanly on _stop_event
                break

            except asyncio.CancelledError:
                logger.debug("Binance WS task cancelled")
                break

            except Exception as exc:
                self.is_connected = False
                logger.warning(
                    f"Binance WS session ended: {exc}. "
                    f"Reconnecting in {self._reconnect_delay}s…"
                )

            if not self._stop_event.is_set():
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self.MAX_BACKOFF
                )

        self.is_connected = False
        logger.info("Binance WS connect loop exited")

    async def _run_session(self) -> None:
        """
        One full WebSocket session via python-binance.
        Raises on error so the outer loop can reconnect.
        """
        self._client = await AsyncClient.create(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        try:
            bsm = BinanceSocketManager(self._client)
            streams = self._build_streams()
            logger.info(f"Opening multiplex_socket with {len(streams)} streams")

            async with bsm.multiplex_socket(streams) as mux:
                self.is_connected = True
                self._reconnect_delay = self.BASE_BACKOFF
                logger.info(
                    f"✓ Connected to Binance WebSocket — "
                    f"{len(streams)} streams active"
                )

                while not self._stop_event.is_set():
                    try:
                        msg = await asyncio.wait_for(mux.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        logger.debug("Binance WS: 30 s keepalive (no data)")
                        continue

                    if not msg:
                        continue

                    # Multiplex messages arrive as {"stream":"…","data":{…}}
                    stream_name = msg.get("stream", "")
                    data = msg.get("data", msg)

                    try:
                        await self.message_handler(data, stream_name)
                    except Exception as exc:
                        logger.error(f"Message handler error: {exc}", exc_info=True)

        finally:
            await self._close_client()

    async def _close_client(self) -> None:
        if self._client:
            try:
                await self._client.close_connection()
            except Exception:
                pass
            self._client = None

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start the WebSocket session in a background task."""
        self._stop_event.clear()
        self._reconnect_delay = self.BASE_BACKOFF
        self._task = asyncio.create_task(self._connect_loop())
        logger.info("BinanceWebSocketClient task scheduled")

    async def stop(self) -> None:
        """Gracefully stop the client."""
        logger.info("Stopping Binance WebSocket client…")
        self._stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        await self._close_client()
        self.is_connected = False
        logger.info("✓ Binance WebSocket client stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected,
            "subscribed_pairs": list(self.trading_pairs),
            "stream_types": self.stream_types,
            "reconnect_delay": self._reconnect_delay,
            "task_done": self._task.done() if self._task else True,
        }
