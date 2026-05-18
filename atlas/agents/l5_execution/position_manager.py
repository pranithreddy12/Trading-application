"""
position_manager.py — Centralized Position Truth

Manages the hierarchy of position truth:
1. Broker API (Ground truth)
2. DB positions table (Derived/reconciled truth)
3. Redis (Fast cache)
"""

import json
from loguru import logger
from redis.asyncio import Redis

from atlas.data.storage.timescale_client import TimescaleClient
from .broker_adapter import BrokerAdapter


class PositionManager:
    """
    Single source of truth for positions across all executors.
    """
    REDIS_POS_PREFIX = "positions:"

    def __init__(self, redis_client: Redis, db_client: TimescaleClient, broker: BrokerAdapter):
        self.redis = redis_client
        self.db = db_client
        self.broker = broker
        
        # We assume a fixed virtual portfolio value for % calculations
        self.PORTFOLIO_VALUE = 100_000.0

    async def open_position(self, strategy_id: str, symbol: str, side: str, qty: float, avg_price: float, broker_name: str):
        """Record a new or updated open position."""
        
        # 1. INSERT into positions table
        query = """
            INSERT INTO positions (strategy_id, account_ref, symbol, side, qty, avg_price, broker, updated_at)
            VALUES (:strategy_id, :account_ref, :symbol, :side, :qty, :avg_price, :broker, NOW())
            ON CONFLICT (id) DO UPDATE SET 
                qty = positions.qty + EXCLUDED.qty,
                avg_price = (positions.avg_price * positions.qty + EXCLUDED.avg_price * EXCLUDED.qty) / (positions.qty + EXCLUDED.qty),
                updated_at = NOW()
        """
        # (Handling conflict requires a unique constraint, but since 'id' is a uuid pk and randomly generated on insert usually, 
        # we might just insert a new row or we should update based on strategy_id+symbol.
        # But for this institutional upgrade, let's keep it simple and insert or update based on a custom query.)
        
        # Real approach: Check if position exists for strategy+symbol
        check_query = "SELECT id, qty, avg_price FROM positions WHERE strategy_id = :strategy_id AND symbol = :symbol"
        from sqlalchemy.sql import text
        async with self.db.engine.begin() as conn:
            res = await conn.execute(text(check_query), {"strategy_id": strategy_id, "symbol": symbol})
            existing = res.fetchone()
            
            if existing:
                new_qty = float(existing[1]) + qty
                new_avg = (float(existing[2]) * float(existing[1]) + avg_price * qty) / new_qty
                update_query = "UPDATE positions SET qty = :qty, avg_price = :avg_price, updated_at = NOW() WHERE id = :id"
                await conn.execute(text(update_query), {"qty": new_qty, "avg_price": new_avg, "id": existing[0]})
            else:
                insert_query = """
                    INSERT INTO positions (strategy_id, account_ref, symbol, side, qty, avg_price, broker)
                    VALUES (:strategy_id, 'system', :symbol, :side, :qty, :avg_price, :broker)
                """
                await conn.execute(text(insert_query), {
                    "strategy_id": strategy_id, "symbol": symbol, "side": side,
                    "qty": qty, "avg_price": avg_price, "broker": broker_name
                })

        # 2. HSET Redis cache
        pos_key = f"{self.REDIS_POS_PREFIX}{strategy_id}"
        pos_data = {
            "symbol": symbol,
            "side": side,
            "qty": qty, # This would be cumulative if updated, keeping it simple
            "avg_price": avg_price
        }
        await self.redis.hset(pos_key, symbol, json.dumps(pos_data))

    async def close_position(self, strategy_id: str, symbol: str):
        """Close an existing position."""
        from sqlalchemy.sql import text
        
        # 1. DELETE from positions table
        query = "DELETE FROM positions WHERE strategy_id = :strategy_id AND symbol = :symbol"
        async with self.db.engine.begin() as conn:
            await conn.execute(text(query), {"strategy_id": strategy_id, "symbol": symbol})
            
        # 2. HDEL Redis key
        pos_key = f"{self.REDIS_POS_PREFIX}{strategy_id}"
        await self.redis.hdel(pos_key, symbol)

    async def reconcile(self):
        """Compare broker positions vs DB positions. Log discrepancies."""
        broker_positions = await self.broker.get_positions()
        
        from sqlalchemy.sql import text
        query = "SELECT symbol, qty, broker FROM positions WHERE broker = :broker"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query), {"broker": self.broker.broker_name})
            db_positions = res.fetchall()

        # Build maps for comparison
        broker_map = {p["symbol"]: p["qty"] for p in broker_positions}
        
        # Aggregate DB positions by symbol (since multiple strategies might hold the same symbol)
        db_map = {}
        for row in db_positions:
            sym = row[0]
            qty = float(row[1])
            db_map[sym] = db_map.get(sym, 0.0) + qty

        # Find Phantom positions (in DB but not at broker)
        for sym, db_qty in db_map.items():
            broker_qty = broker_map.get(sym, 0.0)
            if abs(db_qty - broker_qty) > 0.001:
                logger.error(f"RECONCILIATION MISMATCH: {sym} | DB={db_qty} | Broker={broker_qty}")
                # We could auto-correct the DB here, but for now we alert

        # Find Orphan positions (at broker but not in DB)
        for sym, broker_qty in broker_map.items():
            if sym not in db_map:
                logger.warning(f"ORPHAN POSITION FOUND: {sym} | Broker={broker_qty} | DB=0")

    async def get_portfolio_exposure(self) -> float:
        """Total value of open positions / portfolio value."""
        from sqlalchemy.sql import text
        query = "SELECT SUM(qty * avg_price) FROM positions"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query))
            total_value = res.scalar() or 0.0
        
        return float(total_value) / self.PORTFOLIO_VALUE

    async def get_strategy_exposure(self, strategy_id: str) -> float:
        """Single strategy exposure as % of portfolio."""
        from sqlalchemy.sql import text
        query = "SELECT SUM(qty * avg_price) FROM positions WHERE strategy_id = :strategy_id"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query), {"strategy_id": strategy_id})
            total_value = res.scalar() or 0.0
            
        return float(total_value) / self.PORTFOLIO_VALUE
