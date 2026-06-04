"""
broker_adapter.py — Broker-agnostic execution abstraction layer.

All broker API calls MUST flow through a BrokerAdapter implementation.
Direct HTTP calls to broker APIs outside this layer are prohibited.

Adapters:
  - AlpacaAdapter  — Alpaca paper/live (REST, urllib)
  - BinanceAdapter — Binance testnet/live (REST, aiohttp, HMAC)
  - SimulatorAdapter — Local fill simulation (no network)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import ssl
import time
import urllib.request
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional
from urllib.parse import urlencode

from loguru import logger
from sqlalchemy.sql import text

from atlas.config.settings import settings


class BrokerAdapter(ABC):
    """Abstract broker adapter. Every concrete adapter MUST implement all methods."""

    broker_name: str = ""

    @abstractmethod
    async def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> dict:
        """
        Submit an order to the broker.
        Returns: {"id": broker_order_id, "status": str, ...}
        Raises on network/API failure.
        """

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> dict:
        """
        Get current order status from broker.
        Returns: {"id": str, "status": str, "filled_qty": float,
                  "filled_avg_price": float, ...}
        """

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> dict:
        """Cancel a specific order. Returns order data or empty dict."""

    @abstractmethod
    async def cancel_all_orders(self) -> None:
        """Cancel ALL open orders at the broker."""

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """
        Get all open positions from broker (ground truth).
        Returns: [{"symbol": str, "qty": float, "side": str,
                   "avg_price": float, "market_value": float}, ...]
        """

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float | None:
        """Get latest price for a symbol. Returns None on failure."""

    @abstractmethod
    async def get_open_orders(self) -> list[dict]:
        """Get all open/pending orders from broker."""


# ─────────────────────────────────────────────────────────────
# ALPACA ADAPTER
# ─────────────────────────────────────────────────────────────

class AlpacaAdapter(BrokerAdapter):
    """
    Alpaca paper/live adapter using urllib (no aiohttp dependency).
    Reuses the proven HTTP logic from the original AlpacaExecutor.
    """

    broker_name = "alpaca"

    PAPER_BASE = "https://paper-api.alpaca.markets"
    DATA_BASE = "https://data.alpaca.markets"

    def __init__(self):
        self._ssl_ctx = ssl.create_default_context()
        self._headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        }

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=self._headers)
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
            return json.loads(resp.read())

    def _post(self, url: str, payload: dict) -> dict:
        headers = {**self._headers, "Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
            return json.loads(resp.read())

    def _delete(self, url: str) -> dict | None:
        req = urllib.request.Request(url, headers=self._headers, method="DELETE")
        try:
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
                body = resp.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return {}
            raise

    async def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> dict:
        loop = asyncio.get_event_loop()
        payload = {
            "symbol": symbol,
            "qty": str(int(qty)) if qty == int(qty) else str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "client_order_id": client_order_id,
        }
        url = f"{self.PAPER_BASE}/v2/orders"
        data = await loop.run_in_executor(None, self._post, url, payload)
        logger.info(f"Alpaca order submitted: {data.get('id')} client_oid={client_order_id}")
        return data

    async def get_order_status(self, broker_order_id: str) -> dict:
        loop = asyncio.get_event_loop()
        url = f"{self.PAPER_BASE}/v2/orders/{broker_order_id}"
        return await loop.run_in_executor(None, self._get, url)

    async def cancel_order(self, broker_order_id: str) -> dict:
        loop = asyncio.get_event_loop()
        url = f"{self.PAPER_BASE}/v2/orders/{broker_order_id}"
        return await loop.run_in_executor(None, self._delete, url) or {}

    async def cancel_all_orders(self) -> None:
        loop = asyncio.get_event_loop()
        url = f"{self.PAPER_BASE}/v2/orders"
        await loop.run_in_executor(None, self._delete, url)
        logger.info("Alpaca: cancelled all open orders")

    async def get_positions(self) -> list[dict]:
        loop = asyncio.get_event_loop()
        url = f"{self.PAPER_BASE}/v2/positions"
        raw = await loop.run_in_executor(None, self._get, url)
        return [
            {
                "symbol": p["symbol"],
                "qty": float(p["qty"]),
                "side": p["side"],
                "avg_price": float(p["avg_entry_price"]),
                "market_value": float(p.get("market_value", 0)),
                "unrealized_pnl": float(p.get("unrealized_pl", 0)),
            }
            for p in raw
        ]

    async def get_current_price(self, symbol: str) -> float | None:
        loop = asyncio.get_event_loop()
        try:
            url = f"{self.DATA_BASE}/v2/stocks/{symbol}/trades/latest"
            data = await loop.run_in_executor(None, self._get, url)
            return float(data["trade"]["p"])
        except Exception as e:
            logger.error(f"Alpaca price fetch failed for {symbol}: {e}")
            return None

    async def get_open_orders(self) -> list[dict]:
        loop = asyncio.get_event_loop()
        url = f"{self.PAPER_BASE}/v2/orders?status=open"
        return await loop.run_in_executor(None, self._get, url)


# ─────────────────────────────────────────────────────────────
# BINANCE ADAPTER
# ─────────────────────────────────────────────────────────────

class BinanceAdapter(BrokerAdapter):
    """
    Binance testnet adapter using aiohttp + HMAC signing.
    Reuses proven signing logic from the original BinanceExecutor.
    """

    broker_name = "binance"

    def __init__(self, base_url: str = "https://testnet.binance.vision"):
        self.base_url = base_url
        self.api_key = settings.binance_api_key
        self.secret_key = settings.binance_secret

    def _sign(self, payload: dict) -> str:
        query_string = urlencode(payload)
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    async def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "MARKET",
        time_in_force: str = "GTC",
    ) -> dict:
        import aiohttp

        payload = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": round(qty, 6),
            "newClientOrderId": client_order_id,
            "timestamp": int(time.time() * 1000),
        }
        query = self._sign(payload)
        url = f"{self.base_url}/api/v3/order?{query}"
        headers = {"X-MBX-APIKEY": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise RuntimeError(f"Binance order failed {resp.status}: {text}")
                data = await resp.json()
                # Normalize to common format
                fills = data.get("fills", [])
                avg_price = 0.0
                if fills:
                    total = sum(float(f["price"]) * float(f["qty"]) for f in fills)
                    total_qty = float(data.get("executedQty", 1))
                    avg_price = total / total_qty if total_qty > 0 else 0
                return {
                    "id": str(data.get("orderId")),
                    "status": data.get("status", "").lower(),
                    "filled_qty": float(data.get("executedQty", 0)),
                    "filled_avg_price": avg_price,
                    "client_order_id": client_order_id,
                }

    async def get_order_status(self, broker_order_id: str) -> dict:
        import aiohttp

        # Binance requires symbol for order query — store in metadata
        # For now, query all open orders and find by orderId
        payload = {"timestamp": int(time.time() * 1000)}
        query = self._sign(payload)
        url = f"{self.base_url}/api/v3/openOrders?{query}"
        headers = {"X-MBX-APIKEY": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    orders = await resp.json()
                    for o in orders:
                        if str(o.get("orderId")) == broker_order_id:
                            return {
                                "id": broker_order_id,
                                "status": o.get("status", "").lower(),
                                "filled_qty": float(o.get("executedQty", 0)),
                            }
        return {"id": broker_order_id, "status": "unknown"}

    async def cancel_order(self, broker_order_id: str) -> dict:
        # Would need symbol — simplified for now
        return {}

    async def cancel_all_orders(self) -> None:
        import aiohttp

        payload = {"timestamp": int(time.time() * 1000)}
        query = self._sign(payload)
        url = f"{self.base_url}/api/v3/openOrders?{query}"
        headers = {"X-MBX-APIKEY": self.api_key}
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info("Binance: cancelled all open orders")

    async def get_positions(self) -> list[dict]:
        import aiohttp

        payload = {"timestamp": int(time.time() * 1000)}
        query = self._sign(payload)
        url = f"{self.base_url}/api/v3/account?{query}"
        headers = {"X-MBX-APIKEY": self.api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    balances = data.get("balances", [])
                    return [
                        {
                            "symbol": b["asset"],
                            "qty": float(b["free"]) + float(b["locked"]),
                            "side": "long",
                            "avg_price": 0,
                            "market_value": 0,
                        }
                        for b in balances
                        if float(b["free"]) + float(b["locked"]) > 0
                    ]
        return []

    async def get_current_price(self, symbol: str) -> float | None:
        import aiohttp

        url = f"{self.base_url}/api/v3/ticker/price?symbol={symbol}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("price", 0))
        return None

    async def get_open_orders(self) -> list[dict]:
        import aiohttp

        payload = {"timestamp": int(time.time() * 1000)}
        query = self._sign(payload)
        url = f"{self.base_url}/api/v3/openOrders?{query}"
        headers = {"X-MBX-APIKEY": self.api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        return []


# ─────────────────────────────────────────────────────────────
# SIMULATOR ADAPTER
# ─────────────────────────────────────────────────────────────

class SimulatorAdapter(BrokerAdapter):
    """
    Local fill simulator — no network calls.
    Used for testing, CI/CD, and development.
    Compatible with CopyTrader's LocalSimulatorAdapter pattern.

    When db_client is provided, fills use real market prices from
    market_data_l1 instead of a static default_price.
    """

    broker_name = "simulator"

    def __init__(
        self,
        default_price: float = 500.0,
        fill_latency_ms: int = 50,
        db_client: Any = None,
    ):
        self._default_price = default_price
        self._fill_latency = fill_latency_ms / 1000.0
        self._orders: dict[str, dict] = {}
        self._positions: list[dict] = []
        self._db = db_client

    async def _get_real_price(self, symbol: str) -> float | None:
        """Fetch latest close price from market_data_l1, falling back to default_price."""
        if self._db is None:
            return None
        try:
            async with self._db.engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT close FROM market_data_l1 WHERE symbol = :sym ORDER BY time DESC LIMIT 1"),
                    {"sym": symbol},
                )
                row = res.fetchone()
                if row is not None:
                    return float(row[0])
        except Exception as exc:
            logger.debug(f"SimulatorAdapter: price fetch failed for {symbol}: {exc}")
        return None

    async def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> dict:
        await asyncio.sleep(self._fill_latency)

        # Use real market price when available, fall back to default_price
        fill_price = await self._get_real_price(symbol)
        if fill_price is None:
            fill_price = self._default_price
            logger.debug(f"SimulatorAdapter: using default_price={self._default_price} for {symbol}")
        else:
            logger.debug(f"SimulatorAdapter: using real price {fill_price} for {symbol}")

        order_id = str(uuid.uuid4())
        order = {
            "id": order_id,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "status": "filled",
            "filled_qty": qty,
            "filled_avg_price": fill_price,
        }
        self._orders[order_id] = order
        # Track simulated position
        self._positions.append({
            "symbol": symbol, "qty": qty, "side": side,
            "avg_price": fill_price, "market_value": qty * fill_price,
        })
        return order

    async def get_order_status(self, broker_order_id: str) -> dict:
        return self._orders.get(broker_order_id, {"id": broker_order_id, "status": "unknown"})

    async def cancel_order(self, broker_order_id: str) -> dict:
        order = self._orders.get(broker_order_id, {})
        if order:
            order["status"] = "cancelled"
        return order

    async def cancel_all_orders(self) -> None:
        for oid, order in self._orders.items():
            if order.get("status") not in ("filled", "cancelled"):
                order["status"] = "cancelled"

    async def get_positions(self) -> list[dict]:
        return list(self._positions)

    async def get_current_price(self, symbol: str) -> float | None:
        # Try real price first, fall back to default
        real = await self._get_real_price(symbol)
        if real is not None:
            return real
        return self._default_price

    async def get_open_orders(self) -> list[dict]:
        return [o for o in self._orders.values() if o.get("status") not in ("filled", "cancelled")]
