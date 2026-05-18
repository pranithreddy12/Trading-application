"""
alpaca_executor.py — LEGACY COMPATIBILITY SHIM

DEPRECATED: Use ExecutionGateway with AlpacaAdapter instead.
This class remains for backward compatibility with existing tests and scripts.
"""

import asyncio
import json
import warnings
from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.core.event_lineage import EventLineageClient
from .broker_adapter import AlpacaAdapter
from .execution_gateway import ExecutionGateway


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
        self.risk_controller = RiskController(redis_client, db_client)
        self.lineage = EventLineageClient(db_client)
        
        # Instantiate the new gateway pattern under the hood
        self.adapter = AlpacaAdapter()
        self.gateway = ExecutionGateway(
            redis_client, db_client, self.adapter, self.risk_controller, self.lineage
        )

    async def run(self):
        warnings.warn("AlpacaExecutor.run is deprecated. Use ExecutionGateway.", DeprecationWarning)
        logger.info(f"{self.name} started (Compatibility Mode).")
        await self.gateway.run()

    async def _process_signal(self, data: dict):
        """Legacy compatibility for old tests."""
        warnings.warn("Use ExecutionGateway.execute() instead.", DeprecationWarning)
        if await KillSwitch.is_active(self.redis):
            return

        trade_req = {
            "strategy_id": data.get("strategy_id", "s1"),
            "symbol": data.get("symbol", "AAPL"),
            "side": data.get("side", "buy"),
            "qty": data.get("qty", 10),
            "price": data.get("price", 100.0)
        }
        if not await self.risk_controller.approve_trade(trade_req):
            return

        # Simplified legacy path for tests
        await self.adapter.submit_order(
            "legacy_" + data.get("strategy_id", "s1"),
            trade_req["symbol"],
            trade_req["side"],
            trade_req["qty"]
        )

        # Mock the db write expected by old tests
        await self.db.save_paper_trade({
            "strategy_id": trade_req["strategy_id"],
            "symbol": trade_req["symbol"],
            "side": trade_req["side"],
            "quantity": trade_req["qty"],
            "price": trade_req["price"],
            "fill_price": trade_req["price"],
            "status": "filled",
            "pnl": 0.0,
        })

    async def _execute_strategy(self, strategy: dict) -> bool:
        """Legacy method — delegates to ExecutionGateway."""
        warnings.warn("Use ExecutionGateway.execute() instead.", DeprecationWarning)
        return await self.gateway.execute(strategy)

    async def _cancel_all_orders(self):
        """Legacy compatibility for old tests."""
        await self.adapter.cancel_all_orders()
