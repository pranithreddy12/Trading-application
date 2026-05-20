"""
order_tracker.py — Idempotent order tracking and state machine.

Ensures that every strategy execution has a deterministic order_key.
Guarantees duplicate deployment prevention using Redis sets and locks.
Logs all state transitions immutably to the execution_log table.
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger
from redis.asyncio import Redis

from atlas.data.storage.timescale_client import TimescaleClient


class OrderState(str, Enum):
    SIGNAL_RECEIVED = "signal_received"
    RISK_APPROVED = "risk_approved"
    RISK_REJECTED = "risk_rejected"
    KILL_SWITCH_BLOCKED = "kill_switch_blocked"
    SUBMITTED = "submitted"
    BROKER_ACK = "broker_ack"
    SUBMISSION_FAILED = "submission_failed"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    FILL_TIMEOUT = "fill_timeout"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    POSITION_OPEN = "position_open"
    POSITION_CLOSED = "position_closed"
    DEAD_LETTER = "dead_letter"

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state in {
            cls.FILLED.value,
            cls.CANCELLED.value,
            cls.DEAD_LETTER.value,
            cls.RISK_REJECTED.value,
            cls.KILL_SWITCH_BLOCKED.value,
            cls.POSITION_CLOSED.value,
        }


class OrderTracker:
    """
    Idempotent order tracking with Redis + DB dual persistence.

    Distributed Execution Governance (Phase 12.7):
    - Redis distributed locking with lease TTL
    - Multi-instance ownership tracking (instance_id)
    - Failover-safe order handling via heartbeat-based lease renewal
    """

    REDIS_SET = "execution:processed_orders"
    REDIS_LOCK_PREFIX = "execution:lock:"
    REDIS_LEASE_PREFIX = "execution:lease:"
    REDIS_OWNERSHIP_PREFIX = "execution:ownership:"
    DEFAULT_LEASE_TTL = 30  # seconds
    MAX_LEASE_TTL = 120     # seconds max

    def __init__(self, redis_client: Redis, db_client: TimescaleClient, instance_id: Optional[str] = None):
        self.redis = redis_client
        self.db = db_client
        self.instance_id = instance_id or self._generate_instance_id()

    def make_order_key(self, strategy: dict) -> str:
        """
        Generate a deterministic uniqueness key for an order.
        Format: {strategy_id}:{symbol}:{side}:{signal_hash}:{date}
        """
        sid = str(strategy.get("id", "unknown"))[:8]
        params = strategy.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}

        symbol = params.get("symbol", "UNKNOWN")
        side = params.get("side", "buy").lower()  # default entry side
        date = datetime.utcnow().strftime("%Y%m%d")

        # Hash entry conditions or parameters to ensure distinct signals are caught
        # If entry_conditions isn't present, hash the whole params dict (excluding volatile fields if any)
        entry_data = str(params.get("entry_conditions", params))
        sig_hash = hashlib.sha256(entry_data.encode("utf-8")).hexdigest()[:8]

        return f"{sid}:{symbol}:{side}:{sig_hash}:{date}"

    def make_client_order_id(self, order_key: str) -> str:
        """
        Generate a valid client_order_id for broker submission (max 48 chars).
        Using a deterministic hash of the order_key ensures broker-level idempotency.
        """
        key_hash = hashlib.sha256(order_key.encode("utf-8")).hexdigest()[:16]
        return f"atlas_{key_hash}"

    async def is_processed(self, order_key: str) -> bool:
        """Check if this order key has already reached a terminal state today."""
        return await self.redis.sismember(self.REDIS_SET, order_key)

    def _generate_instance_id(self) -> str:
        import socket
        import os
        host = socket.gethostname()
        pid = os.getpid()
        return f"{host}:{pid}"

    async def acquire_lock(self, order_key: str, ttl: int = 60) -> bool:
        """
        Prevent concurrent execution of the same order_key.
        Uses Redis SET NX with instance_id as value for ownership tracking.
        Returns True if lock acquired, False if already locked.
        """
        lock_key = f"{self.REDIS_LOCK_PREFIX}{order_key}"
        acquired = await self.redis.set(lock_key, self.instance_id, nx=True, ex=ttl)
        if acquired:
            # Establish lease for distributed execution governance
            await self._establish_lease(order_key, ttl)
            await self._record_ownership(order_key)
        return bool(acquired)

    async def acquire_lease(self, order_key: str, ttl: Optional[int] = None) -> bool:
        """
        Acquire an execution lease for multi-instance ownership.
        Returns True if lease acquired, False if held by another instance.
        """
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        ttl = ttl or self.DEFAULT_LEASE_TTL
        acquired = await self.redis.set(lease_key, self.instance_id, nx=True, ex=ttl)
        return bool(acquired)

    async def _establish_lease(self, order_key: str, ttl: int) -> None:
        """Establish an execution lease with the given TTL."""
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        await self.redis.set(lease_key, self.instance_id, ex=min(ttl, self.MAX_LEASE_TTL))

    async def _record_ownership(self, order_key: str) -> None:
        """Record which instance owns this order for failover recovery."""
        ownership_key = f"{self.REDIS_OWNERSHIP_PREFIX}{order_key}"
        await self.redis.set(ownership_key, self.instance_id, ex=86400)  # 24h ownership record

    async def renew_lease(self, order_key: str, ttl: Optional[int] = None) -> bool:
        """
        Renew an execution lease. Used by long-running operations.
        Returns True if lease was renewed, False if lost (e.g., expired).
        """
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        ttl = ttl or self.DEFAULT_LEASE_TTL
        current = await self.redis.get(lease_key)
        if current and current.decode() == self.instance_id:
            await self.redis.expire(lease_key, min(ttl, self.MAX_LEASE_TTL))
            return True
        return False

    async def get_lease_owner(self, order_key: str) -> Optional[str]:
        """Get the instance that currently holds the lease for an order."""
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        owner = await self.redis.get(lease_key)
        return owner.decode() if owner else None

    async def is_lease_alive(self, order_key: str) -> bool:
        """Check if lease is still active (for failover detection)."""
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        exists = await self.redis.exists(lease_key)
        return bool(exists)

    async def get_lost_orders(self) -> list[str]:
        """
        Find orders that were owned by this instance but whose leases expired.
        Used for failover-safe recovery on startup.
        """
        # Scan for ownership keys belonging to this instance
        pattern = f"{self.REDIS_OWNERSHIP_PREFIX}*"
        cursor = 0
        lost = []
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                owner = await self.redis.get(key_str)
                if owner and owner.decode() == self.instance_id:
                    # Extract order_key from ownership key
                    order_key = key_str.replace(self.REDIS_OWNERSHIP_PREFIX, "", 1)
                    # Check if lease is still alive
                    if not await self.is_lease_alive(order_key):
                        lost.append(order_key)
            if cursor == 0:
                break
        return lost

    async def release_lock(self, order_key: str) -> None:
        """Release the concurrency lock and associated lease."""
        lock_key = f"{self.REDIS_LOCK_PREFIX}{order_key}"
        lease_key = f"{self.REDIS_LEASE_PREFIX}{order_key}"
        await self.redis.delete(lock_key)
        await self.redis.delete(lease_key)

    async def transition(
        self,
        order_key: str,
        state: OrderState,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        broker_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        broker_name: str = "alpaca",
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Record a state transition in the execution_log.
        If terminal, mark as processed in Redis.
        """
        logger.debug(f"Order {order_key} transitioning to {state.value}")

        # 1. Write to DB (requires updating TimescaleClient to support this)
        try:
            await self._write_execution_log(
                order_key=order_key,
                strategy_id=strategy_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                state=state.value,
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                broker=broker_name,
                error_message=error_message,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to write execution log for {order_key}: {e}")
            # We don't raise here to avoid crashing the execution flow just for logging,
            # but in a strict institutional setup, we might queue this or fail hard.

        # 2. Mark in Redis SET on terminal states
        if OrderState.is_terminal(state.value):
            await self.redis.sadd(self.REDIS_SET, order_key)
            # 7 day TTL for idempotency cache to clear out old keys
            await self.redis.expire(self.REDIS_SET, 86400 * 7)

    async def _write_execution_log(
        self,
        order_key: str,
        state: str,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        broker_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        broker: str = "alpaca",
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Internal helper to write the log row."""
        query = """
            INSERT INTO execution_log (
                order_key, strategy_id, symbol, side, quantity, price, 
                state, broker_order_id, client_order_id, broker, 
                error_message, metadata
            ) VALUES (
                :order_key, :strategy_id, :symbol, :side, :quantity, :price, 
                :state, :broker_order_id, :client_order_id, :broker, 
                :error_message, :metadata
            )
        """
        params = {
            "order_key": order_key,
            "strategy_id": strategy_id,
            "symbol": symbol or "UNKNOWN",
            "side": side or "UNKNOWN",
            "quantity": float(quantity) if quantity is not None else None,
            "price": float(price) if price is not None else None,
            "state": state,
            "broker_order_id": broker_order_id,
            "client_order_id": client_order_id,
            "broker": broker,
            "error_message": error_message,
            "metadata": json.dumps(metadata) if metadata else None,
        }
        # Assuming we add _execute_insert_raw to timescale_client if needed, 
        # but we can just use the existing engine context
        from sqlalchemy.sql import text
        async with self.db.engine.begin() as conn:
            await conn.execute(text(query), params)
