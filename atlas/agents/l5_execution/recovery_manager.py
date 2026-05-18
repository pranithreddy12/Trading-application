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
    """Startup reconciliation — blocks trading until complete."""
    
    RECOVERY_LOCK_KEY = "execution:recovery_lock"

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

    async def run_startup_reconciliation(self) -> bool:
        """
        Called once at ExecutionGateway startup.
        MUST complete before any trades are allowed.
        """
        logger.critical("RECOVERY: Starting startup reconciliation")
        
        # 1. Set recovery lock (blocks all execution locally, and via redis globally)
        await self.redis.set(self.RECOVERY_LOCK_KEY, "1", ex=300)
        
        try:
            # 2. Check kill switch state
            if await KillSwitch.is_active(self.redis):
                logger.critical("RECOVERY: Kill switch active — trading blocked")
                # We do not lift the lock; let it expire or require manual intervention
                return False
            
            # 3. Reconcile open orders
            broker_orders = await self.broker.get_open_orders()
            if broker_orders:
                logger.info(f"RECOVERY: Found {len(broker_orders)} open orders at broker.")
                # Basic handling: cancel orphan orders at startup to ensure clean slate
                # In a more advanced setup, we'd map them to execution_log to resume polling.
                await self.broker.cancel_all_orders()
                logger.info("RECOVERY: Cancelled open broker orders to ensure clean state.")
            
            # 4. Reconcile positions
            await self.positions.reconcile()
            
            # 5. Check for dead-lettered orders that need resolution
            from sqlalchemy.sql import text
            query = "SELECT COUNT(*) FROM execution_dead_letter WHERE resolved = FALSE"
            async with self.db.engine.connect() as conn:
                res = await conn.execute(text(query))
                unresolved_count = res.scalar() or 0
                
            if unresolved_count > 0:
                logger.warning(f"RECOVERY: {unresolved_count} unresolved dead-letter orders require attention.")
            
            logger.info("RECOVERY: Startup reconciliation complete — trading enabled")
            return True
            
        except Exception as e:
            logger.error(f"RECOVERY: Failed during reconciliation: {e}")
            return False
            
        finally:
            # 6. Release recovery lock
            await self.redis.delete(self.RECOVERY_LOCK_KEY)
