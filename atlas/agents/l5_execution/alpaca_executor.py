import asyncio
import json
import urllib.request
import ssl
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings


class AlpacaExecutor(BaseAgent):
    name = "AlpacaExecutor"
    agent_type = "executor"
    layer = "L5"

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.redis = redis_client
        self._ssl_ctx = ssl.create_default_context()

    async def run(self):
        logger.info(f"{self.name} started.")
        while self.status == "running":
            await asyncio.sleep(1)

    async def _execute_strategy(self, strategy: dict) -> bool:
        strategy_id = str(strategy["id"])
        name = strategy.get("name", "unknown")

        try:
            ks_active = await self.redis.hget("kill_switch:state", "active")
            if ks_active == b"1":
                logger.warning(f"Kill switch active — skipping {name}")
                return False

            spec = strategy.get("parameters") or strategy.get("spec") or {}
            if isinstance(spec, str):
                spec = json.loads(spec)

            asset_class = spec.get("asset_class", "equity")
            if asset_class == "crypto":
                logger.info(f"Skipping crypto strategy {name} — use BinanceExecutor")
                return False

            symbol = spec.get("symbol") or settings.watchlist.split(",")[0].strip()

            price = await self._get_current_price(symbol)
            if not price:
                logger.error(f"Could not get price for {symbol}")
                return False

            portfolio_value = 100000
            position_value = portfolio_value * 0.10
            qty = max(1, int(position_value / price))
            side = "buy"

            order = await self._submit_order(symbol, qty, side)
            if not order:
                return False

            fill = await self._wait_for_fill(order["id"])

            await self.db.save_paper_trade(
                {
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": qty,
                    "price": price,
                    "fill_price": fill.get("filled_avg_price", price),
                    "status": "filled",
                    "pnl": 0.0,
                }
            )

            await self.db.update_strategy_status(
                strategy_id, "paper_trading", "First paper trade placed"
            )

            logger.info(
                f"EXECUTED: {symbol} {side} {qty} shares @ "
                f"${float(fill.get('filled_avg_price', price)):.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"Execution failed for {name}: {e}")
            return False

    def _urllib_get(self, url: str, headers: dict) -> dict:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
            return json.loads(resp.read())

    def _urllib_post(self, url: str, headers: dict, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
            return json.loads(resp.read())

    async def _get_current_price(self, symbol: str) -> float | None:
        loop = asyncio.get_event_loop()
        try:
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest"
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }
            data = await loop.run_in_executor(None, self._urllib_get, url, headers)
            return float(data["trade"]["p"])
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def _submit_order(self, symbol: str, qty: int, side: str) -> dict | None:
        loop = asyncio.get_event_loop()
        try:
            url = "https://paper-api.alpaca.markets/v2/orders"
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
                "Content-Type": "application/json",
            }
            payload = {
                "symbol": symbol,
                "qty": str(qty),
                "side": side,
                "type": "market",
                "time_in_force": "day",
            }
            data = await loop.run_in_executor(
                None, self._urllib_post, url, headers, payload
            )
            logger.info(f"Order submitted: {data['id']}")
            return data
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None

    async def _wait_for_fill(self, order_id: str, timeout: int = 30) -> dict:
        loop = asyncio.get_event_loop()
        url = f"https://paper-api.alpaca.markets/v2/orders/{order_id}"
        headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        }
        for _ in range(timeout // 2):
            try:
                data = await loop.run_in_executor(None, self._urllib_get, url, headers)
                if data.get("status") == "filled":
                    return data
            except Exception:
                pass
            await asyncio.sleep(2)
        return {}
