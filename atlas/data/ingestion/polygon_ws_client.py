"""
Polygon.io WebSocket Client with correct auth handshake and exponential backoff.

Polygon handshake sequence (server-driven):
  1. Client connects (TCP)
  2. Server  → [{"ev":"status","status":"connected","message":"…"}]
  3. Client  → {"action":"auth","params":"<API_KEY>"}
  4. Server  → [{"ev":"status","status":"auth_success","message":"…"}]
  5. Client  → {"action":"subscribe","params":"Q.AAPL,T.AAPL,A.AAPL,…"}
  6. Server  → one or more [{"ev":"status","status":"success",…}] messages
  7. Server  → real-time market data frames (Q / T / A)

Streams:
  Q.* — quotes  (bid/ask)
  T.* — trades  (individual prints)
  A.* — aggregates (1-minute OHLCV bars)
"""

import asyncio
import json
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime, timezone
from loguru import logger

import websockets
import websockets.exceptions


class PolygonWebSocketClient:
    """
    Async WebSocket client for Polygon.io real-time stock data.

    Key fixes vs previous version:
      * Drains the initial "connected" status frame before sending auth
      * Drains subscription confirmation frames before entering the data loop
      * Proper exponential backoff across the outer reconnect loop
      * _stop_event drives clean shutdown at every await point
    """

    WS_REALTIME = "wss://socket.polygon.io/stocks"
    WS_DELAYED = "wss://delayed.polygon.io/stocks"

    BASE_BACKOFF: int = 2  # seconds
    MAX_BACKOFF: int = 60  # seconds
    RECV_TIMEOUT: float = 45.0  # Polygon sends heartbeat ~every 30 s

    def __init__(
        self,
        api_key: str,
        symbols: List[str],
        message_handler: Callable[[Dict[str, Any]], Any],
        stream_types: Optional[List[str]] = None,
        delayed: bool = True,
    ):
        self.api_key = api_key
        self.symbols = symbols
        self.message_handler = message_handler
        self.stream_types = stream_types or ["Q", "T", "A"]
        self.WS_URL = self.WS_DELAYED if delayed else self.WS_REALTIME

        self.is_connected: bool = False
        self.is_authenticated: bool = False
        self._subscribed_symbols: set = set()
        self._retry_count: int = 0

        self._stop_event = asyncio.Event()
        self._reconnect_delay: int = self.BASE_BACKOFF
        self._task: Optional[asyncio.Task] = None

        logger.info(
            f"PolygonWebSocketClient ready — "
            f"symbols={symbols}, streams={self.stream_types}"
        )

    # ------------------------------------------------------------------ #
    #  Connection loop
    # ------------------------------------------------------------------ #

    async def _connect_loop(self) -> None:
        """Outer loop: reconnect with exponential backoff until stopped."""
        logger.info("Polygon WebSocket connect loop starting…")

        while not self._stop_event.is_set():
            try:
                await self._run_session()
                break  # clean exit (stop requested inside session)

            except asyncio.CancelledError:
                logger.debug("Polygon WS task cancelled")
                break

            except Exception as exc:
                self.is_connected = False
                self.is_authenticated = False
                logger.warning(
                    f"Polygon WS session ended: {exc}. "
                    f"Reconnecting in {self._reconnect_delay}s…"
                )

            if not self._stop_event.is_set():
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self.MAX_BACKOFF)
                self._retry_count += 1

        self.is_connected = False
        self.is_authenticated = False
        logger.info("Polygon WS connect loop exited")

    async def _run_session(self) -> None:
        """
        One full WebSocket session:
          connect → drain "connected" → auth → subscribe → listen
        """
        logger.info(f"Connecting to Polygon WS: {self.WS_URL}")

        async with websockets.connect(
            self.WS_URL,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            self.is_connected = True
            self._reconnect_delay = self.BASE_BACKOFF
            self._retry_count = 0
            logger.info("✓ TCP connection established to Polygon")

            # Step 1 — drain server's initial "connected" frame
            await self._drain_connected(ws)

            # Step 2 — authenticate
            await self._authenticate(ws)

            # Step 3 — subscribe
            await self._subscribe(ws)

            # Step 4 — data loop
            await self._listen(ws)

    # ------------------------------------------------------------------ #
    #  Handshake helpers
    # ------------------------------------------------------------------ #

    async def _drain_connected(self, ws) -> None:
        """
        Consume the initial status frame Polygon sends immediately on connect.

        Frame: [{"ev":"status","status":"connected","message":"Connected Successfully"}]
        If we don't read this before sending auth, the auth response check will
        see this frame instead of auth_success and fail.
        """
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=8.0)
            frames = json.loads(raw)
            if isinstance(frames, list):
                for f in frames:
                    logger.debug(f"Polygon initial frame: {f}")
                    if f.get("status") == "connected":
                        logger.info("✓ Polygon: received 'connected' status frame")
                        return
            logger.warning(f"Unexpected initial frame(s): {frames}")
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout waiting for Polygon 'connected' frame — proceeding anyway"
            )

    async def _authenticate(self, ws) -> None:
        """Send API key and wait for auth_success."""
        await ws.send(json.dumps({"action": "auth", "params": self.api_key}))
        logger.debug("Sent auth message")

        # Polygon may send extra status frames; loop until auth_success or error
        deadline = asyncio.get_event_loop().time() + 8.0
        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                raise ConnectionError("Timeout waiting for Polygon auth response")

            frames = json.loads(raw)
            if not isinstance(frames, list):
                frames = [frames]

            for frame in frames:
                status = frame.get("status", "")
                if status == "auth_success":
                    self.is_authenticated = True
                    logger.info("✓ Authenticated with Polygon WebSocket")
                    return
                elif status in ("auth_failed", "auth_timeout"):
                    raise ConnectionError(f"Polygon auth failed: {frame}")
                else:
                    logger.debug(f"Auth intermediate frame: {frame}")

        raise ConnectionError("Did not receive auth_success within timeout")

    async def _subscribe(self, ws) -> None:
        """Send subscription and drain confirmation frames."""
        subs = [f"{stype}.{sym}" for sym in self.symbols for stype in self.stream_types]

        await ws.send(json.dumps({"action": "subscribe", "params": ",".join(subs)}))
        logger.info(f"Sent subscribe for {len(subs)} streams")

        # Drain confirmation frames (success/already-subscribed) with a short window.
        # Do NOT block indefinitely — real data may arrive immediately.
        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                break  # no more confirmations

            frames = json.loads(raw)
            if not isinstance(frames, list):
                frames = [frames]

            for frame in frames:
                ev = frame.get("ev")
                st = frame.get("status", "")
                if st == "success":
                    logger.debug(f"Subscription confirmed: {frame.get('message', '')}")
                elif ev in ("Q", "T", "A"):
                    # Real data arrived before all confirmations — route it
                    try:
                        await self.message_handler(frame)
                    except Exception as exc:
                        logger.error(f"Early message handler error: {exc}")
                else:
                    logger.debug(f"Subscribe frame: {frame}")

        self._subscribed_symbols = set(self.symbols)
        logger.info(f"✓ Subscribed — {len(self.symbols)} symbols active")

    # ------------------------------------------------------------------ #
    #  Data loop
    # ------------------------------------------------------------------ #

    async def _listen(self, ws) -> None:
        """Main receive loop — passes market data frames to message_handler."""
        logger.info("Polygon WebSocket: entering data loop")

        while not self._stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=self.RECV_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("Polygon WS: no data in 45 s — forcing reconnect")
                return
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning(f"Polygon WS connection closed: {exc}")
                return

            try:
                frames = json.loads(raw)
                if not isinstance(frames, list):
                    frames = [frames]

                for frame in frames:
                    if self._is_market_data(frame):
                        await self.message_handler(frame)
                    # Silently drop status / heartbeat frames
            except json.JSONDecodeError:
                logger.warning(f"JSON decode error: {raw[:120]}")
            except Exception as exc:
                logger.error(f"Message handler error: {exc}", exc_info=True)

    @staticmethod
    def _is_market_data(frame: Dict[str, Any]) -> bool:
        return isinstance(frame, dict) and frame.get("ev") in ("Q", "T", "A")

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._connect_loop())
        logger.info("PolygonWebSocketClient task scheduled")

    async def stop(self) -> None:
        logger.info("Stopping Polygon WebSocket client…")
        self._stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        self.is_connected = False
        self.is_authenticated = False
        logger.info("✓ Polygon WebSocket client stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected,
            "authenticated": self.is_authenticated,
            "subscribed_symbols": list(self._subscribed_symbols),
            "retry_count": self._retry_count,
            "stream_types": self.stream_types,
            "task_done": self._task.done() if self._task else True,
        }
