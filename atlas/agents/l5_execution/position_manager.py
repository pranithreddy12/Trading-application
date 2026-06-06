"""
position_manager.py — Centralized Position Truth & Lifecycle Engine

Manages the hierarchy of position truth:
1. Broker API (Ground truth)
2. DB positions table (Derived/reconciled truth)
3. Redis (Fast cache)

Priority 1 & 2 Implementation:
- Mark-to-Market PnL tracking
- Position Lifecycle Engine (Monitor -> Exit)
"""

import json
import asyncio
from datetime import datetime
from loguru import logger
from redis.asyncio import Redis

from atlas.data.storage.timescale_client import TimescaleClient
from .broker_adapter import BrokerAdapter
from sqlalchemy.sql import text


class PositionManager:
    """
    Single source of truth for positions across all executors.
    """

    REDIS_POS_PREFIX = "positions:"

    def __init__(
        self, redis_client: Redis, db_client: TimescaleClient, broker: BrokerAdapter
    ):
        self.redis = redis_client
        self.db = db_client
        self.broker = broker

        # We assume a fixed virtual portfolio value for % calculations
        self.PORTFOLIO_VALUE = 100_000.0
        self._monitoring = False

    async def start_monitoring(self):
        self._monitoring = True
        asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        self._monitoring = False

    async def _monitor_loop(self):
        """Background task for Mark-to-Market PnL and exit conditions."""
        logger.info("Position Lifecycle Engine started.")
        while self._monitoring:
            try:
                await self.update_mark_to_market()
            except Exception as e:
                logger.error(f"Error in MTM loop: {e}")
            await asyncio.sleep(10)  # Check every 10 seconds

    async def update_mark_to_market(self):
        """Calculate Unrealized PnL and enforce exit conditions."""
        async with self.db.engine.begin() as conn:
            # Get all open positions
            r = await conn.execute(
                text(
                    "SELECT id, strategy_id, symbol, side, qty, avg_price, trace_id, feature_snapshot_id FROM positions"
                )
            )
            positions = r.fetchall()

            if not positions:
                return

            # Group symbols to fetch latest prices efficiently
            symbols = list({p[2] for p in positions})
            r_prices = await conn.execute(
                text(
                    "SELECT DISTINCT ON (symbol) symbol, close FROM market_data_l1 WHERE symbol = ANY(:symbols) ORDER BY symbol, time DESC"
                ),
                {"symbols": symbols},
            )
            prices = {row[0]: float(row[1]) for row in r_prices.fetchall()}

            for pos in positions:
                pid, sid, sym, side, qty, avg_price, tid, fsid = pos
                qty = float(qty)
                avg_price = float(avg_price)

                current_price = prices.get(sym)
                if current_price is None:
                    continue

                # Calculate Unrealized PnL
                if side == "buy":
                    unrealized_pnl = qty * (current_price - avg_price)
                    pct_move = (current_price - avg_price) / avg_price
                else:
                    unrealized_pnl = qty * (avg_price - current_price)
                    pct_move = (avg_price - current_price) / avg_price

                # Update MTM PnL in DB
                await conn.execute(
                    text(
                        """
                        UPDATE positions
                        SET
                            current_price = :cp,
                            unrealized_pnl = :pnl,
                            last_mark_time = NOW()
                        WHERE id = :id
                        """
                    ),
                    {
                        "cp": current_price,
                        "pnl": unrealized_pnl,
                        "id": pid,
                    },
                )

                # Enforce Exit Conditions (Stop Loss / Take Profit)
                # Example: Stop Loss at -5%, Take Profit at +10%
                if pct_move <= -0.05 or pct_move >= 0.10:
                    exit_reason = "take_profit" if pct_move >= 0.10 else "stop_loss"
                    logger.info(
                        f"Position {sym} ({sid}) triggered {exit_reason} at {current_price}"
                    )
                    # In a fully connected system, we'd emit an exit signal here.
                    # For demo purposes, we will close it directly.
                    await self._execute_exit(
                        conn,
                        sid,
                        sym,
                        side,
                        qty,
                        current_price,
                        unrealized_pnl,
                        exit_reason,
                        trace_id=tid,
                        feature_snapshot_id=fsid,
                    )

    async def _execute_exit(
        self,
        conn,
        strategy_id,
        symbol,
        side,
        qty,
        exit_price,
        realized_pnl,
        reason,
        trace_id=None,
        feature_snapshot_id=None,
    ):
        """Simulate closing a position and recording the realized trade."""
        exit_side = "sell" if side == "buy" else "buy"
        logger.info(
            f"EXIT_EXECUTED "
            f"symbol={symbol} "
            f"reason={reason} "
            f"pnl={realized_pnl:.2f} "
            f"price={exit_price} "
            f"qty={qty} "
            f"side={exit_side} "
            f"strategy={strategy_id[:8]}"
        )
        import uuid

        # Insert exit trade into paper_trades
        await conn.execute(
            text("""
            INSERT INTO paper_trades (id, time, strategy_id, symbol, side, quantity, price, fill_price, status, pnl, trace_id, feature_snapshot_id)
            VALUES (:id, NOW(), :sid, :sym, :side, :qty, :p, :fp, 'filled', :pnl, :tid, :fsid)
            """),
            {
                "id": str(uuid.uuid4()),
                "sid": strategy_id,
                "sym": symbol,
                "side": exit_side,
                "qty": qty,
                "p": exit_price,
                "fp": exit_price,
                "pnl": realized_pnl,
                "tid": trace_id,
                "fsid": feature_snapshot_id,
            },
        )

        # Remove from positions
        await conn.execute(
            text("DELETE FROM positions WHERE strategy_id = :sid AND symbol = :sym"),
            {"sid": strategy_id, "sym": symbol},
        )

        # Remove from Redis
        pos_key = f"{self.REDIS_POS_PREFIX}{strategy_id}"
        await self.redis.hdel(pos_key, symbol)

    async def active_position_exists(self, strategy_id: str, symbol: str) -> bool:
        """Check if an active position already exists to prevent duplicate activations."""
        query = (
            "SELECT 1 FROM positions WHERE strategy_id = :sid AND symbol = :sym LIMIT 1"
        )
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query), {"sid": strategy_id, "sym": symbol})
            return res.fetchone() is not None

    async def open_position(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        qty: float,
        avg_price: float,
        broker_name: str,
        trace_id=None,
        feature_snapshot_id=None,
    ) -> float:
        """Record a new or updated open position, handling buys and sells correctly. Returns realized PnL."""
        check_query = "SELECT id, side, qty, avg_price, trace_id, feature_snapshot_id FROM positions WHERE strategy_id = :strategy_id AND symbol = :symbol"
        realized_pnl = 0.0
        async with self.db.engine.begin() as conn:
            res = await conn.execute(
                text(check_query), {"strategy_id": strategy_id, "symbol": symbol}
            )
            existing = res.fetchone()

            if existing:
                pid, existing_side, existing_qty, existing_avg_price, tid, fsid = (
                    existing
                )
                existing_qty = float(existing_qty)
                existing_avg_price = float(existing_avg_price)

                if existing_side.lower() == side.lower():
                    # Increasing existing position
                    new_qty = existing_qty + qty
                    new_avg = (
                        existing_avg_price * existing_qty + avg_price * qty
                    ) / new_qty
                    update_query = "UPDATE positions SET qty = :qty, avg_price = :avg_price, updated_at = NOW(), trace_id = :tid, feature_snapshot_id = :fsid WHERE id = :id"
                    await conn.execute(
                        text(update_query),
                        {
                            "qty": new_qty,
                            "avg_price": new_avg,
                            "id": pid,
                            "tid": trace_id,
                            "fsid": feature_snapshot_id,
                        },
                    )
                else:
                    # Reducing or closing existing position
                    if qty >= existing_qty:
                        # Full close
                        realized_pnl = (
                            existing_qty * (avg_price - existing_avg_price)
                            if existing_side.lower() == "buy"
                            else existing_qty * (existing_avg_price - avg_price)
                        )
                        await conn.execute(
                            text("DELETE FROM positions WHERE id = :id"), {"id": pid}
                        )
                    else:
                        # Partial close
                        realized_pnl = (
                            qty * (avg_price - existing_avg_price)
                            if existing_side.lower() == "buy"
                            else qty * (existing_avg_price - avg_price)
                        )
                        new_qty = existing_qty - qty
                        update_query = "UPDATE positions SET qty = :qty, updated_at = NOW() WHERE id = :id"
                        await conn.execute(
                            text(update_query), {"qty": new_qty, "id": pid}
                        )
            else:
                # New position
                insert_query = """
                    INSERT INTO positions (strategy_id, account_ref, symbol, side, qty, avg_price, broker, unrealized_pnl, realized_pnl, trace_id, feature_snapshot_id)
                    VALUES (:strategy_id, 'system', :symbol, :side, :qty, :avg_price, :broker, 0.0, 0.0, :tid, :fsid)
                """
                await conn.execute(
                    text(insert_query),
                    {
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "avg_price": avg_price,
                        "broker": broker_name,
                        "tid": trace_id,
                        "fsid": feature_snapshot_id,
                    },
                )

        pos_key = f"{self.REDIS_POS_PREFIX}{strategy_id}"
        if (
            existing
            and existing[1].lower() != side.lower()
            and qty >= float(existing[2])
        ):
            await self.redis.hdel(pos_key, symbol)
        else:
            pos_data = {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "avg_price": avg_price,
            }
            await self.redis.hset(pos_key, symbol, json.dumps(pos_data))

        return float(realized_pnl)

    async def close_position(self, strategy_id: str, symbol: str):
        """Close an existing position."""
        query = "DELETE FROM positions WHERE strategy_id = :strategy_id AND symbol = :symbol"
        async with self.db.engine.begin() as conn:
            await conn.execute(
                text(query), {"strategy_id": strategy_id, "symbol": symbol}
            )

        pos_key = f"{self.REDIS_POS_PREFIX}{strategy_id}"
        await self.redis.hdel(pos_key, symbol)

    async def reconcile(self):
        """Compare broker positions vs DB positions. Log discrepancies."""
        broker_positions = await self.broker.get_positions()

        query = "SELECT symbol, qty, broker FROM positions WHERE broker = :broker"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query), {"broker": self.broker.broker_name})
            db_positions = res.fetchall()

        broker_map = {p["symbol"]: p["qty"] for p in broker_positions}

        db_map = {}
        for row in db_positions:
            sym = row[0]
            qty = float(row[1])
            db_map[sym] = db_map.get(sym, 0.0) + qty

        for sym, db_qty in db_map.items():
            broker_qty = broker_map.get(sym, 0.0)
            if abs(db_qty - broker_qty) > 0.001:
                logger.error(
                    f"RECONCILIATION MISMATCH: {sym} | DB={db_qty} | Broker={broker_qty}"
                )

        for sym, broker_qty in broker_map.items():
            if sym not in db_map:
                logger.warning(
                    f"ORPHAN POSITION FOUND: {sym} | Broker={broker_qty} | DB=0"
                )

    async def get_portfolio_exposure(self) -> float:
        """Total value of open positions / portfolio value."""
        query = "SELECT SUM(qty * avg_price) FROM positions"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query))
            total_value = res.scalar() or 0.0

        return float(total_value) / self.PORTFOLIO_VALUE

    async def get_strategy_exposure(self, strategy_id: str) -> float:
        """Single strategy exposure as % of portfolio."""
        query = "SELECT SUM(qty * avg_price) FROM positions WHERE strategy_id = :strategy_id"
        async with self.db.engine.connect() as conn:
            res = await conn.execute(text(query), {"strategy_id": strategy_id})
            total_value = res.scalar() or 0.0

        return float(total_value) / self.PORTFOLIO_VALUE
