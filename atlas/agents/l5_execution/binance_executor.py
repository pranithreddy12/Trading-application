import asyncio
import json
import time
import hmac
import hashlib
import aiohttp
from urllib.parse import urlencode
from loguru import logger
from redis.asyncio import Redis
from atlas.core.agent_base import BaseAgent
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.data.storage.timescale_client import TimescaleClient

class BinanceExecutor(BaseAgent):
    name = "BinanceExecutor"
    agent_type = "executor"
    layer = "L5"
    BINANCE_BASE_URL = "https://testnet.binance.vision"

    def __init__(self, redis_client: Redis, db_client: TimescaleClient = None):
        super().__init__(self.name, self.agent_type, self.layer, redis_client)
        self.db_client = db_client
        self.risk_controller = RiskController(redis_client, db_client)
        self.api_key = "dummy"
        self.secret_key = "dummy"
        
        try:
            from atlas.config import settings
            if hasattr(settings, 'BINANCE_API_KEY'):
                self.api_key = settings.BINANCE_API_KEY
                self.secret_key = settings.BINANCE_SECRET
        except Exception:
            pass

    def _sign_request(self, payload: dict) -> str:
        query_string = urlencode(payload)
        signature = hmac.new(self.secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return f"{query_string}&signature={signature}"

    async def run(self):
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("strategy_signals", "risk_alerts")
        
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"].decode()
                data = json.loads(message["data"])
                
                if channel == "risk_alerts" and data.get("type") == "KILL_SWITCH_ACTIVATED":
                    await self._cancel_all_orders()
                    
                elif channel == "strategy_signals" and data.get("type") == "validated":
                    await self._process_signal(data)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe()

    async def _process_signal(self, data: dict):
        if await KillSwitch.is_active(self._redis):
            logger.warning("Kill switch active, aborting Binance trade.")
            return

        strategy_id = data.get("strategy_id", "unknown")
        symbol = data.get("symbol")
        side = data.get("side", "buy").upper()
        raw_qty = data.get("qty", 1.0)

        # Handle quantity precision (round to 6 decimal places)
        qty = round(float(raw_qty), 6)
        
        # Handle min notional (order value >= 10 USDT)
        price_estimate = data.get("price", 100.0)
        if qty * price_estimate < 10.0:
            logger.warning(f"Order value < 10 USDT for {symbol}. Adjusting qty.")
            qty = round(10.5 / price_estimate, 6)

        request = {"symbol": symbol, "side": side, "qty": qty, "size": qty, "price": price_estimate}
        if not await self.risk_controller.approve_trade(request):
            return

        order_payload = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": qty,
            "timestamp": int(time.time() * 1000)
        }
        
        query_str = self._sign_request(order_payload)
        url = f"{self.BINANCE_BASE_URL}/api/v3/order?{query_str}"
        headers = {"X-MBX-APIKEY": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    logger.error(f"Failed to place binance order: {await resp.text()}")
                    return
                order_data = await resp.json()
                order_id = order_data.get("orderId")
                
                if order_data.get("status") == "FILLED":
                    # calc avg fill price
                    fills = order_data.get("fills", [])
                    if fills:
                        fill_price = sum(float(f["price"]) * float(f["qty"]) for f in fills) / float(order_data.get("executedQty", 1))
                    else:
                        fill_price = float(order_data.get("price", 0))
                else:
                    fill_price = await self._poll_order(session, symbol, order_id, headers)

        if fill_price is not None:
            if self.db_client:
                query = "INSERT INTO paper_trades (time, strategy_id, symbol, side, qty, fill_price, pnl) VALUES (NOW(), :s_id, :sym, :side, :qty, :price, :pnl)"
                params = {"s_id": strategy_id, "sym": symbol, "side": side, "qty": qty, "price": fill_price, "pnl": 0.0}
                await self.db_client._execute_insert(query, params)
                
            fill_event = {
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "fill_price": fill_price,
                "timestamp": int(time.time()),
                "pnl": 0.0
            }
            await self._redis.publish("execution_fills", json.dumps(fill_event))

    async def _poll_order(self, session, symbol, order_id, headers):
        for _ in range(30):
            await asyncio.sleep(0.1)
            payload = {"symbol": symbol, "orderId": order_id, "timestamp": int(time.time() * 1000)}
            query_str = self._sign_request(payload)
            async with session.get(f"{self.BINANCE_BASE_URL}/api/v3/order?{query_str}", headers=headers) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    if status_data.get("status") == "FILLED":
                        ex_qty = float(status_data.get("executedQty", 1))
                        cum_quote = float(status_data.get("cummulativeQuoteQty", 0))
                        return cum_quote / ex_qty if ex_qty > 0 else 0
        return None

    async def _cancel_all_orders(self):
        payload = {"timestamp": int(time.time() * 1000)}
        query_str = self._sign_request(payload)
        url = f"{self.BINANCE_BASE_URL}/api/v3/openOrders?{query_str}"
        headers = {"X-MBX-APIKEY": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info("Cancelled all open orders on Binance.")
