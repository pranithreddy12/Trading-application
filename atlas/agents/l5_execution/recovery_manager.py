"""
recovery_manager.py — Startup Reconciliation & Recovery Lock

Ensures that ATLAS cannot execute new trades until:
1. Kill switch states are validated
2. Orphan orders are cancelled
3. Positions are reconciled
4. Unresolved dead letters are alerted
"""

from loguru import logger
from redis.asyncio import Redis

from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.data.storage.timescale_client import TimescaleClient
from .broker_adapter import BrokerAdapter
from .order_tracker import OrderTracker, OrderState
from .position_manager import PositionManager
from .dead_letter import DeadLetterManager


class RecoveryManager:
    """Startup reconciliation — blocks trading until complete.

    Distributed Execution Governance (Phase 12.7):
    - Failover-safe order handling: recover lost orders from other instances
    - Multi-instance ownership detection via lease inspection
    - Dead-letter recovery for orphaned orders from expired leases
    - Startup reconciliation that scans for expired leases across instances
    """
    
    RECOVERY_LOCK_KEY = "execution:recovery_lock"
    MAX_LEASE_AGE_SECONDS = 120  # Max time a lease can be alive before considered stale

    def __init__(
        self,
        redis_client: Redis,
        db_client: TimescaleClient,
        broker: BrokerAdapter,
        tracker: OrderTracker,
        positions: PositionManager,
        dead_letter: DeadLetterManager
    ):
        self.redis = redis_client
        self.db = db_client
        self.broker = broker
        self.tracker = tracker
        self.positions = positions
        self.dead_letter = dead_letter
        self.execution_locked = False

    async def run_startup_reconciliation(self) -> bool:
        """
        Called once at ExecutionGateway startup.
        MUST complete before any trades are allowed.

        Distributed governance enhancements:
        - Scans for expired leases across ALL instances (failover detection)
        - Recovers orphaned orders from dead instances
        - Dead-letter reconciliation for orders with stale ownership
        """
        logger.critical("RECOVERY: Starting startup reconciliation")
        self.execution_locked = True
        
        # 1. Set recovery lock (blocks all execution locally, and via redis globally)
        await self.redis.set(self.RECOVERY_LOCK_KEY, "1", ex=300)
        
        release_lock = True
        try:
            # 2. Check kill switch state
            halted = await self.db.fetchval(
                """
                SELECT halted
                FROM risk_state
                WHERE scope = 'portfolio'
                LIMIT 1
                """
            )
            if halted:
                logger.critical("RECOVERY: Kill switch active — trading blocked")
                self.execution_locked = True
                release_lock = False
                # We do not lift the lock; let it expire or require manual intervention
                return False
            
            # 3. Reconcile open orders
            broker_orders = await self.broker.get_open_orders()
            if broker_orders:
                logger.info(f"RECOVERY: Found {len(broker_orders)} open orders at broker.")
                # Basic handling: cancel orphan orders at startup to ensure clean slate
                await self.broker.cancel_all_orders()
                logger.info("RECOVERY: Cancelled open broker orders to ensure clean state.")
            
            # 4. Reconcile positions
            await self.positions.reconcile()
            
            # 5. Failover-safe: detect and recover orders with expired leases
            # Scan for all ownership keys to find leases that have expired
            await self._recover_expired_leases()
            
            # 6. Check for dead-lettered orders that need resolution
            from sqlalchemy.sql import text
            query = "SELECT COUNT(*) FROM execution_dead_letter WHERE resolved = FALSE"
            async with self.db.engine.connect() as conn:
                res = await conn.execute(text(query))
                unresolved_count = res.scalar() or 0
                
            if unresolved_count > 0:
                logger.warning(f"RECOVERY: {unresolved_count} unresolved dead-letter orders require attention.")
            
            logger.info("RECOVERY: Startup reconciliation complete — trading enabled")
            self.execution_locked = False
            return True
            
        except Exception as e:
            logger.error(f"RECOVERY: Failed during reconciliation: {e}")
            self.execution_locked = True
            return False
            
        finally:
            # 7. Release recovery lock
            if release_lock:
                await self.redis.delete(self.RECOVERY_LOCK_KEY)

    async def _recover_expired_leases(self) -> None:
        """
        Scan for orders with expired leases and recover them.
        This provides failover-safe recovery across multi-instance deployments.
        """
        try:
            # Scan all execution leases
            pattern = "execution:lease:*"
            cursor = 0
            recovered_count = 0
            while True:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                for key_bytes in keys:
                    key = key_bytes.decode() if isinstance(key_bytes, bytes) else key_bytes
                    # Check TTL: if lease is expired or near expiration (< 10s)
                    ttl = await self.redis.ttl(key)
                    lease_key = key.replace("execution:lease:", "", 1)
                    if ttl <= 10:
                        # Lease is expired or about to expire → recover
                        owner = await self.redis.get(key)
                        owner_str = owner.decode() if owner else "unknown"
                        logger.warning(f"RECOVERY: Found expired lease for {lease_key} (owner={owner_str}) — recovering")
                        # Mark as dead letter so recovery completes cleanly
                        await self.tracker.transition(
                            lease_key, OrderState.DEAD_LETTER,
                            error_message=f"lease_expired_owner={owner_str}"
                        )
                        recovered_count += 1
                if cursor == 0:
                    break
            if recovered_count > 0:
                logger.warning(f"RECOVERY: Recovered {recovered_count} expired leases from failover")
        except Exception as e:
            logger.warning(f"RECOVERY: Expired lease recovery failed: {e}")
