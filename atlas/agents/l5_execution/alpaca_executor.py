import asyncio
import json
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
            redis_client=redis_client
        )
        self.db = db_client
        self.redis = redis_client

    async def run(self):
        """
        Main run loop for AlpacaExecutor.
        In this implementation, it is driven by external script or orchestration,
        but it can also listen to strategy_signals if needed.
        """
        logger.info(f"{self.name} started.")
        while self.status == "running":
            await asyncio.sleep(1)

    async def _execute_strategy(self, strategy: dict) -> bool:
        """Execute one validated strategy as a paper trade"""
        strategy_id = str(strategy["id"])
        name = strategy.get("name", "unknown")

        try:
            # 1. Kill switch check
            ks_active = await self.redis.hget("kill_switch:state", "active")
            if ks_active == b"1":
                logger.warning(f"Kill switch active — skipping {name}")
                return False

            # 2. Parse spec to get asset class and preferred symbol
            spec = strategy.get("parameters") or strategy.get("spec") or {}
            if isinstance(spec, str):
                import json
                spec = json.loads(spec)

            asset_class = spec.get("asset_class", "equity")
            if asset_class == "crypto":
                logger.info(f"Skipping crypto strategy {name} — use BinanceExecutor")
                return False

            # 3. Pick symbol from watchlist
            symbol = spec.get("symbol") or settings.watchlist.split(",")[0].strip()

            # 4. Get current price from Alpaca data API
            price = await self._get_current_price(symbol)
            if not price:
                logger.error(f"Could not get price for {symbol}")
                return False

            # 5. Calculate quantity: 10% of $100k portfolio
            portfolio_value = 100000
            position_value = portfolio_value * 0.10
            qty = max(1, int(position_value / price))
            side = "buy"  # default for paper demo

            # 6. Submit paper order
            order = await self._submit_order(symbol, qty, side)
            if not order:
                return False

            # 7. Poll for fill (max 30s)
            fill = await self._wait_for_fill(order["id"])

            # 8. Save to paper_trades
            await self.db.save_paper_trade({
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": side,
                "quantity": qty,
                "price": price,
                "fill_price": fill.get("filled_avg_price", price),
                "status": "filled",
                "pnl": 0.0
            })

            # 9. Update strategy status
            await self.db.update_strategy_status(
                strategy_id, "paper_trading", "First paper trade placed"
            )

            logger.info(
                f"✅ EXECUTED: {symbol} {side} {qty} shares @ "
                f"${float(fill.get('filled_avg_price', price)):.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"Execution failed for {name}: {e}")
            return False

    async def _get_current_price(self, symbol: str) -> float | None:
        """Fetch latest price from Alpaca data API"""
        import aiohttp
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
        headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote = data.get("quote", {})
                    ask = float(quote.get("ap", 0))
                    bid = float(quote.get("bp", 0))
                    return (ask + bid) / 2 if ask and bid else None
                else:
                    logger.error(f"Failed to get price for {symbol}: {resp.status}")
        return None

    async def _submit_order(self, symbol: str, qty: int, side: str) -> dict | None:
        import aiohttp
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
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    logger.info(f"Order submitted: {data['id']}")
                    return data
                else:
                    text = await resp.text()
                    logger.error(f"Order failed {resp.status}: {text}")
        return None

    async def _wait_for_fill(self, order_id: str, timeout: int = 30) -> dict:
        import aiohttp
        url = f"https://paper-api.alpaca.markets/v2/orders/{order_id}"
        headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        }
        for _ in range(timeout // 2):
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "filled":
                            return data
            await asyncio.sleep(2)
        return {}
