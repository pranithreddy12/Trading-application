"""
execution_gateway.py — Central Execution Orchestrator.

This is the ONLY approved execution path.
Flow:
Strategy → OrderTracker → Risk → KillSwitch → BrokerAdapter → PositionManager → Lineage
"""

import asyncio
import random
import time
import uuid
from datetime import datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # stdlib (py>=3.9); tzdata present on this host
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - fallback if tzdata missing
    import pytz
    _ET = pytz.timezone("America/New_York")

from sqlalchemy.sql import text

from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.event_lineage import EventLineageClient
from atlas.core.exit_policy import resolve_exit_policy
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings

from .broker_adapter import BrokerAdapter
from .order_tracker import OrderTracker, OrderState


# --- Issue 1: market-hours gate -------------------------------------------------
_CRYPTO_SUFFIXES = ("USDT", "USDC", "BUSD", "BTC", "ETH")


def _is_crypto(symbol: str) -> bool:
    s = (symbol or "").upper()
    return any(s.endswith(suf) for suf in _CRYPTO_SUFFIXES)


def is_market_open(symbol: str) -> bool:
    """Crypto trades 24/7; US equities only on weekdays 09:30-16:00 ET.

    Prevents placing equity paper orders against a frozen Friday close on
    weekends/after-hours (every fill +$0.00, and duplicate fills accumulating).
    """
    if _is_crypto(symbol):
        return True
    now = datetime.now(_ET)
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
from .position_manager import PositionManager
from .recovery_manager import RecoveryManager
from .dead_letter import DeadLetterManager
from .position_sizer import PositionSizer
from atlas.agents.l3_backtest.regime_selector import RegimeSelector

# Module-level singleton — shared across all gateway instances
_position_sizer = PositionSizer()


class ExecutionGateway(BaseAgent):
    """
    Central execution orchestrator.
    INVARIANTS:
    - The ONLY code path that calls broker APIs.
    - Every order passes through idempotency → risk → kill switch → broker → tracker.
    - Recovery lock blocks execution until startup reconciliation completes.

    Distributed Execution Governance (Phase 12.7):
    - Redis distributed locking with lease TTL
    - Multi-instance ownership tracking via instance_id
    - Failover-safe order handling with lease renewal
    - Periodic heartbeat-based lease maintenance
    - All in-memory execution locks removed (fully distributed)
    """

    name = "ExecutionGateway"
    agent_type = "executor"
    layer = "L5"

    # Lease maintenance interval
    LEASE_RENEWAL_INTERVAL = 15  # seconds

    def __init__(
        self,
        redis_client: Redis,
        db_client: TimescaleClient,
        broker: BrokerAdapter,
        risk: RiskController,
        lineage: EventLineageClient,
        instance_id: Optional[str] = None,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.broker = broker
        self.risk = risk
        self.lineage = lineage
        self.instance_id = instance_id or ""

        self.tracker = OrderTracker(redis_client, db_client, instance_id=instance_id)
        self.positions = PositionManager(redis_client, db_client, broker)

        # Issue 2: per-(symbol, side) cooldown to block duplicate simultaneous
        # fills (multiple strategies firing the same signal in the same second).
        self._last_trade_ts: dict[tuple[str, str], float] = {}
        self._TRADE_COOLDOWN_S: float = 30.0
        self.dead_letter = DeadLetterManager(redis_client, db_client)
        self.recovery = RecoveryManager(
            redis_client,
            db_client,
            broker,
            self.tracker,
            self.positions,
            self.dead_letter,
        )

        self._recovery_complete = False
        self._active_lease_order_keys: set[str] = set()
        self._MAX_ACTIVE_LEASES = 1000
        self._lease_maintenance_task: Optional[asyncio.Task] = None
        self._background_tasks: set[asyncio.Task] = set()

        # Scout intelligence cache for dynamic execution adaptation
        self._scout_liquidity_regime = ""
        self._scout_execution_regime = ""
        self._scout_cache_time = 0.0
        self._scout_cache_ttl = 60.0  # refresh every minute

    async def _lease_maintenance(self):
        """
        Background task that periodically renews active execution leases.
        Ensures failover-safety: if this instance dies, leases expire and
        another instance can pick them up.
        Also prunes stale entries to prevent unbounded lease set growth.
        """
        while self.status == "running":
            try:
                stale_count = 0
                for order_key in list(self._active_lease_order_keys):
                    # Guard against unbounded growth: if set exceeds MAX, aggressively prune
                    if len(self._active_lease_order_keys) > self._MAX_ACTIVE_LEASES:
                        logger.warning(
                            f"Active lease set size {len(self._active_lease_order_keys)} "
                            f"exceeds MAX ({self._MAX_ACTIVE_LEASES}) — pruning {order_key}"
                        )
                        self._active_lease_order_keys.discard(order_key)
                        stale_count += 1
                        continue

                    renewed = await self.tracker.renew_lease(order_key)
                    if not renewed:
                        logger.warning(
                            f"Lease lost for {order_key} — removing from active set"
                        )
                        self._active_lease_order_keys.discard(order_key)
                        stale_count += 1

                if stale_count > 0:
                    logger.info(
                        f"Lease maintenance: pruned {stale_count} stale entries, "
                        f"{len(self._active_lease_order_keys)} active remaining"
                    )

                await asyncio.sleep(self.LEASE_RENEWAL_INTERVAL)
            except Exception as e:
                logger.debug(f"Lease maintenance cycle failed: {e}")
                await asyncio.sleep(5)

    def _track_background_task(self, task: asyncio.Task) -> asyncio.Task:
        self._background_tasks.add(task)

        def _finalize(done_task: asyncio.Task) -> None:
            self._background_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception(f"{self.name}: background task failed")

        task.add_done_callback(_finalize)
        return task

    async def _shutdown_background_tasks(self) -> None:
        pending = [task for task in self._background_tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._background_tasks.clear()

    async def run(self):
        logger.info(f"{self.name} starting up.")

        # 1. Recovery lock — block until reconciliation passes
        recovery_ok = await self.recovery.run_startup_reconciliation()
        self._recovery_complete = recovery_ok
        if not recovery_ok:
            logger.warning(
                "Recovery reconciliation did not complete; execution remains locked."
            )

        # 1b. Start lease maintenance background task (distributed governance)
        self._lease_maintenance_task = self._track_background_task(
            asyncio.create_task(self._lease_maintenance())
        )

        # 1c. Detect and recover lost orders from this instance (with timeout)
        try:
            lost_orders = await asyncio.wait_for(
                self.tracker.get_lost_orders(), timeout=30.0
            )
            if lost_orders:
                logger.warning(
                    f"Found {len(lost_orders)} lost orders from this instance — marking for recovery"
                )
                for lost_key in lost_orders:
                    await self.tracker.transition(
                        lost_key,
                        OrderState.DEAD_LETTER,
                        error_message="lease_expired_failover_recovery",
                    )
        except asyncio.TimeoutError:
            logger.warning("Lost order recovery timed out (30s) — skipping")
        except Exception as e:
            logger.warning(f"Lost order recovery failed: {e}")

        # 1d. Start Position Lifecycle Engine (Mark-to-Market)
        await self.positions.start_monitoring()

        # 2. Poll for validated strategies (in a real system this might be pub/sub driven)
        # We will subscribe to pubsub for signals
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("strategy_signals")

        try:
            while self.status == "running":
                if not self._recovery_complete:
                    await asyncio.sleep(1)
                    continue

                logger.debug(
                    f"GATEWAY_LOOP_ITERATION | status={self.status} recovery={self._recovery_complete}"
                )

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    logger.debug(
                        f"SIGNAL_RECEIVED_RAW | type={message.get('type')} "
                        f"channel={message.get('channel')} "
                        f"data_type={type(message.get('data')).__name__} "
                        f"data_len={len(message.get('data', b''))} "
                        f"data_preview={message.get('data', b'')[:80]}"
                    )
                if message and message["type"] == "message":
                    try:
                        import json

                        data = json.loads(message["data"])
                        logger.debug(
                            f"SIGNAL_DECODED | type={data.get('type')} "
                            f"strategy_id={data.get('strategy_id')} "
                            f"symbol={data.get('symbol')} "
                            f"side={data.get('side')} "
                            f"keys={list(data.keys())}"
                        )
                        # Expecting {"type": "validated", "strategy_id": "...", ...}
                        if (
                            data.get("type") == "validated"
                            or data.get("type") == "signal"
                        ):
                            strategy_id = data.get("strategy_id")
                            logger.debug(
                                f"{self.name}: Received {data.get('type')} signal for {strategy_id}"
                            )
                            if strategy_id:
                                strategy = await self._get_strategy_by_id(strategy_id)
                                if strategy:
                                    # BRIDGE FIX: Merge dynamic signal data into strategy spec for execution
                                    strategy["symbol"] = data.get("symbol")
                                    strategy["side"] = data.get("side")
                                    strategy["qty"] = data.get("qty")
                                    strategy["feature_snapshot_id"] = data.get(
                                        "feature_snapshot_id"
                                    )

                                    logger.debug(
                                        f"SIGNAL_EXECUTE_START | strategy_id={strategy_id} "
                                        f"symbol={data.get('symbol')} "
                                        f"side={data.get('side')} "
                                        f"qty={data.get('qty')}"
                                    )
                                    logger.info(
                                        f"{self.name}: Triggering execution for {strategy_id} on {strategy.get('symbol')} ({strategy.get('side')})"
                                    )
                                    self._track_background_task(
                                        asyncio.create_task(self.execute(strategy))
                                    )
                                else:
                                    logger.warning(
                                        f"{self.name}: Strategy {strategy_id} not found in DB"
                                    )
                    except Exception as e:
                        logger.error(f"Error processing signal: {e}")

                await asyncio.sleep(0.1)
        finally:
            await self.positions.stop_monitoring()
            await pubsub.unsubscribe()
            await self._shutdown_background_tasks()

    async def _get_strategy_by_id(self, strategy_id: str) -> Optional[dict]:
        from sqlalchemy.sql import text

        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT s.id, s.name, s.parameters, s.status, b.short_window_score
                    FROM strategies s
                    LEFT JOIN backtest_results b ON b.strategy_id = s.id
                    WHERE s.id::text = :id
                    ORDER BY b.start_date DESC NULLS LAST
                    LIMIT 1
                """),
                {"id": strategy_id},
            )
            row = result.fetchone()
            if row:
                return dict(row._mapping)
        return None

    def _build_trade_request(self, strategy: dict) -> dict:
        """Extract needed trade params from strategy spec, allowing overrides."""
        # BRIDGE FIX: Support explicit overrides in strategy dict (from dynamic signals)
        symbol = strategy.get("symbol")
        side = strategy.get("side")
        qty = strategy.get("qty")

        params = strategy.get("parameters", {})
        if isinstance(params, str):
            import json

            try:
                params = json.loads(params)
            except Exception:
                params = {}

        if not symbol:
            symbol = params.get("symbol")
        if not side:
            side = params.get("side", "buy").lower()
        if qty is None:
            qty = params.get("qty")

        asset_class = params.get("asset_class", "equity").lower()

        # Fallback to random symbol from watchlist ONLY if still not specified
        if not symbol:
            settings = get_settings()
            if asset_class == "crypto":
                pairs = (
                    settings.crypto_pairs.split(",")
                    if hasattr(settings, "crypto_pairs")
                    else ["BTCUSDT", "ETHUSDT"]
                )
                symbol = random.choice(pairs)
            else:
                watchlist = (
                    settings.watchlist.split(",")
                    if hasattr(settings, "watchlist")
                    else ["SPY", "QQQ", "AAPL", "NVDA", "MSFT"]
                )
                symbol = random.choice(watchlist)

        if qty is not None:
            logger.warning(
                f"PositionSizer: ignoring signal-specified qty={qty} "
                f"for {symbol} — signals must not specify quantity"
            )

        estimated_price = params.get("estimated_price") or params.get("price") or 0.0
        # PositionSizer's stop_loss_pct is a FRACTION of price, and it must be the
        # SAME stop the position will exit at. params["stop_loss_pct"] is a PERCENT
        # number (e.g. 0.3 == 0.3%); resolve it to a fraction via the shared exit
        # policy so sizing and exits use one stop. (Previously the percent number
        # was passed straight in, so a 0.3% design was mis-sized as a 30% stop.)
        stop_frac = resolve_exit_policy(params)["stop_loss_frac"]
        stop_pct = stop_frac if stop_frac > 0 else None

        return {
            "strategy_id": str(strategy.get("id")),
            "symbol": symbol,
            "side": side.lower(),
            "qty": 0.0,  # Will be sized asynchronously in execute()
            "price": 0.0,  # Filled at market for now
            "estimated_price": float(estimated_price) if estimated_price else 0.0,
            "stop_pct": float(stop_pct) if stop_pct else None,
        }

    async def execute(self, strategy: dict) -> bool:
        logger.debug("entering execute()")
        """
        The constitutional execution path.
        Returns True if fully executed (or already executed), False otherwise.
        """
        # Ensure we have a fresh copy of strategy with all overrides for building trade request
        trade_req = self._build_trade_request(strategy)
        sid = trade_req["strategy_id"]
        sym = trade_req["symbol"]
        side = trade_req["side"]

        # Issue 1: market-hours gate. Skip equity orders when the US market is
        # closed (weekends/after-hours) — otherwise they fill at a frozen close
        # (every PnL +$0.00) and duplicate fills pile up in the trade log.
        if not is_market_open(sym):
            logger.info(f"Market closed for {sym} — skipping order ({side})")
            return False

        # Issue 2: per-(symbol, side) cooldown — block duplicate simultaneous
        # entries from multiple strategies seeing the same signal. The check+set
        # is synchronous (atomic under asyncio) so concurrent coroutines dedupe.
        _cd_key = (sym, side)
        _now = time.monotonic()
        _last = self._last_trade_ts.get(_cd_key)
        if _last is not None and (_now - _last) < self._TRADE_COOLDOWN_S:
            logger.info(
                f"Cooldown: {sym} {side} — "
                f"{self._TRADE_COOLDOWN_S - (_now - _last):.0f}s remaining; skipping duplicate"
            )
            return False
        self._last_trade_ts[_cd_key] = _now

        # 0. Risk-normalized position sizing (Phase 14 Fix)
        # We must obtain a real market price to size the position correctly.
        exec_price = trade_req.get("estimated_price", 0.0)
        stop_pct = trade_req.get("stop_pct")

        if exec_price <= 0:
            try:
                exec_price = float(await self.broker.get_current_price(sym) or 0.0)
            except Exception as e:
                logger.error(f"Failed to fetch live price for {sym}: {e}")
                exec_price = 0.0

        if exec_price <= 0:
            logger.error(
                f"Cannot execute {sym} - unable to determine market price for PositionSizer."
            )
            return False

        qty = _position_sizer.calculate_qty(
            symbol=sym, price=exec_price, stop_loss_pct=stop_pct
        )
        if qty <= 0:
            logger.error(
                f"PositionSizer returned qty 0 for {sym} at ${exec_price:,.2f}"
            )
            return False

        notional = qty * exec_price
        risk_usd = notional * (stop_pct if stop_pct else _position_sizer.STOP_LOSS_PCT)

        logger.warning(
            f"POSITION_SIZER_RESULT "
            f"symbol={sym} "
            f"qty={qty} "
            f"price={exec_price} "
            f"notional=${notional:,.2f} "
            f"risk_usd=${risk_usd:,.2f}"
        )

        trade_req["qty"] = qty
        trade_req["price"] = exec_price  # Store reference price

        # Use a unique key that includes side to avoid collision between entry and exit
        order_key = f"order:{sid}:{sym}:{side}:{uuid.uuid4().hex[:8]}"
        client_order_id = self.tracker.make_client_order_id(order_key)

        # 1. Idempotency gate (simplified for signals)
        if await self.tracker.is_processed(order_key):
            logger.info(f"Order {order_key} already processed.")
            return True

        # Acquire concurrency lock
        if not await self.tracker.acquire_lock(order_key):
            logger.warning(f"Order {order_key} currently locked by another process.")
            return False

        # 1.5 Duplicate Activation Protection (BRIDGE FIX: Allow Closing Trades)
        async with self.db.engine.connect() as conn:
            res = await conn.execute(
                text(
                    "SELECT side, qty FROM positions WHERE strategy_id = :sid AND symbol = :sym LIMIT 1"
                ),
                {"sid": sid, "sym": sym},
            )
            existing_pos = res.fetchone()

        if existing_pos:
            existing_side = existing_pos[0].lower()
            if existing_side == side.lower():
                logger.info(
                    f"Duplicate activation protection: {side} position already exists for {sid} on {sym}. Blocking duplicate entry."
                )
                await self.tracker.transition(
                    order_key,
                    OrderState.CANCELLED,
                    metadata={"reason": "duplicate_position_protection"},
                )
                await self.tracker.release_lock(order_key)
                return False
            else:
                logger.info(
                    f"Allowing closing trade: Strategy {sid} has {existing_side} on {sym}, executing {side} to close."
                )

        try:
            halted = await self.db.fetchval(
                """
                SELECT halted
                FROM risk_state
                WHERE scope = 'portfolio'
                LIMIT 1
                """
            )
            if halted in (True, 1, "1", "true", "TRUE"):
                raise Exception("KILL_SWITCH_ACTIVE")
        except Exception as exc:
            if str(exc) == "KILL_SWITCH_ACTIVE":
                await self.tracker.transition(order_key, OrderState.KILL_SWITCH_BLOCKED)
                logger.warning("Execution blocked by persisted kill switch.")
                return False
            raise

        # Track base state
        await self.tracker.transition(
            order_key,
            OrderState.SIGNAL_RECEIVED,
            strategy_id=sid,
            symbol=sym,
            side=side,
            quantity=qty,
            client_order_id=client_order_id,
            broker_name=self.broker.broker_name,
        )

        # Track lease for distributed governance
        self._active_lease_order_keys.add(order_key)

        try:
            # 2. Scout-aware dynamic adaptation (Phase 10.10)
            await self._refresh_scout_intelligence()

            # Phase 30: Relaxed from hard-reject to soft sizing reduction for dangerous liquidity
            # Use canonical _scout_adjusted_qty() — Phase 30 values: thin=75%, dangerous=25%
            adjusted_qty = self._scout_adjusted_qty(qty)
            if adjusted_qty != qty:
                regime_tag = self._scout_liquidity_regime or self._scout_execution_regime
                logger.warning(
                    f"LIQUIDITY_SCOUT_ADJUSTMENT symbol={sym} "
                    f"regime={regime_tag} "
                    f"pre_qty={qty:.6g} post_qty={adjusted_qty:.6g} "
                    f"reduction={100*(1 - adjusted_qty/qty):.0f}%"
                )
                qty = adjusted_qty

            # 2c. Regime-weighted strategy prioritization
            try:
                regime = await self._get_current_regime()
                selector = RegimeSelector()
                ranked = await selector.get_regime_weighted_ranking(
                    self.db, regime, limit=3
                )
                ranked_ids = {r["strategy_id"] for r in ranked}
                if sid in ranked_ids:
                    logger.info(
                        f"{self.name}: Strategy {sid} matches current regime ({regime})"
                    )
                else:
                    logger.info(
                        f"{self.name}: Strategy {sid} NOT in top-3 for regime "
                        f"({regime}) — executing with standard priority"
                    )
            except Exception as e:
                logger.debug(f"{self.name}: Regime selection skipped: {e}")

            # 2d. Kill switch check
            if await KillSwitch.is_active(self.db):
                await self.tracker.transition(order_key, OrderState.KILL_SWITCH_BLOCKED)
                return False

            # 3a. Notional cap validation (PositionSizer guard)
            # Fetch existing symbol exposure from open positions before approving.
            existing_notional = 0.0
            try:
                async with self.db.engine.connect() as _nc:
                    _nr = await _nc.execute(
                        text(
                            "SELECT COALESCE(SUM(qty * avg_price), 0) "
                            "FROM positions WHERE symbol = :sym"
                        ),
                        {"sym": sym},
                    )
                    existing_notional = float(_nr.scalar() or 0.0)
            except Exception as _ne:
                logger.debug(
                    f"{self.name}: Could not fetch existing notional for {sym}: {_ne}"
                )

            # Get current price from broker for validation
            _price_for_validation = 0.0
            try:
                _ticker = await self.broker.get_current_price(sym)
                _price_for_validation = float(_ticker or 0.0)
            except Exception:
                pass

            if _price_for_validation > 0:
                _approved, _reason = _position_sizer.validate_notional(
                    symbol=sym,
                    qty=qty,
                    price=_price_for_validation,
                    existing_notional=existing_notional,
                )
                if not _approved:
                    logger.warning(
                        f"{self.name}: Order rejected by PositionSizer for {sym}: {_reason}"
                    )
                    await self.tracker.transition(
                        order_key,
                        OrderState.RISK_REJECTED,
                        metadata={"reason": f"position_sizer: {_reason}"},
                    )
                    return False

            # 3b. Risk controller approval
            if not await self.risk.approve_trade(trade_req):
                await self.tracker.transition(
                    order_key,
                    OrderState.RISK_REJECTED,
                    metadata={"reason": "risk_limits_breached"},
                )
                return False

            await self.tracker.transition(order_key, OrderState.RISK_APPROVED)

            # 4. Submit with retry (lease-renewal during long operations)
            order = await self._submit_with_retry(client_order_id, sym, side, qty)
            if not order:
                # Exhausted retries
                fail_reason = "submission_exhausted"
                await self.tracker.transition(
                    order_key, OrderState.DEAD_LETTER, error_message=fail_reason
                )
                await self.dead_letter.record(
                    order_key,
                    sid,
                    sym,
                    side,
                    qty,
                    fail_reason,
                    OrderState.RISK_APPROVED.value,
                    client_order_id=client_order_id,
                    severity="high",
                )
                return False

            broker_oid = order["id"]
            await self.tracker.transition(
                order_key, OrderState.BROKER_ACK, broker_order_id=broker_oid
            )

            # 5. Poll fill with partial awareness
            fill = await self._poll_fill(broker_oid)

            if fill.get("status") in ("filled", "closed"):
                fill_price = fill.get("filled_avg_price", 0.0)
                filled_qty = fill.get("filled_qty", qty)

                await self.tracker.transition(
                    order_key,
                    OrderState.FILLED,
                    broker_order_id=broker_oid,
                    price=fill_price,
                    quantity=filled_qty,
                    metadata=fill,
                )

                # 5.5 Resolve Lineage early to pass it to downstream records
                trace_id = await self.lineage.get_trace_by_strategy(sid)
                feature_snapshot_id = strategy.get("feature_snapshot_id")

                logger.warning(
                    f"FINAL_ORDER_QTY "
                    f"symbol={sym} "
                    f"qty={filled_qty} "
                    f"price={fill_price} "
                    f"notional={filled_qty * fill_price:.2f}"
                )

                # 6. Open position
                logger.debug("before open_position()")
                realized_pnl = await self.positions.open_position(
                    strategy_id=sid,
                    symbol=sym,
                    side=side,
                    qty=filled_qty,
                    avg_price=fill_price,
                    broker_name=self.broker.broker_name,
                    trace_id=trace_id,
                    feature_snapshot_id=feature_snapshot_id,
                )
                logger.debug("after open_position()")

                # 7. Write to paper_trades for historical backwards compat
                # Realized PnL is non-zero only for closing trades
                logger.info(
                    f"PERSISTING TRADE | "
                    f"strategy={sid} "
                    f"symbol={sym} "
                    f"side={side} "
                    f"qty={filled_qty} "
                    f"price={fill_price} "
                    f"pnl={realized_pnl} "
                    f"trace_id={trace_id}"
                )
                await self.db.save_paper_trade(
                    {
                        "strategy_id": sid,
                        "symbol": sym,
                        "side": side,
                        "quantity": filled_qty,
                        "price": fill_price,
                        "fill_price": fill_price,
                        "status": "filled",
                        "pnl": realized_pnl,
                        "trace_id": trace_id,
                        "feature_snapshot_id": feature_snapshot_id,
                        "origin": "execution",
                    }
                )

                logger.info(f"PAPER_TRADE INSERT COMPLETE | sid={sid}")

                # 8. Record Lineage Event
                if trace_id:
                    await self.lineage.create_event(
                        trace_id=trace_id,
                        stage="execution",
                        status="completed",
                        actor="ExecutionGateway",
                        strategy_id=sid,
                        metadata={
                            "broker": self.broker.broker_name,
                            "qty": filled_qty,
                            "price": fill_price,
                        },
                    )

                return True

            elif fill.get("status") == "partially_filled":
                await self.tracker.transition(
                    order_key,
                    OrderState.PARTIALLY_FILLED,
                    broker_order_id=broker_oid,
                    metadata=fill,
                )
                # Need human/system resolution
                await self.dead_letter.record(
                    order_key,
                    sid,
                    sym,
                    side,
                    qty,
                    "partial_fill_abandoned",
                    OrderState.PARTIALLY_FILLED.value,
                    broker_order_id=broker_oid,
                    client_order_id=client_order_id,
                    severity="medium",
                    metadata=fill,
                )
                return False

            else:
                # Handle timeout → cancel
                await self.tracker.transition(
                    order_key, OrderState.FILL_TIMEOUT, broker_order_id=broker_oid
                )
                cancel_res = await self.broker.cancel_order(broker_oid)
                await self.tracker.transition(
                    order_key, OrderState.CANCELLED, broker_order_id=broker_oid
                )
                return False

        except Exception as e:
            logger.error(f"Execution gateway error for {order_key}: {e}")
            await self.tracker.transition(
                order_key, OrderState.DEAD_LETTER, error_message=str(e)
            )
            await self.dead_letter.record(
                order_key,
                sid,
                sym,
                side,
                qty,
                f"unhandled_exception: {e}",
                OrderState.DEAD_LETTER.value,
                client_order_id=client_order_id,
                severity="critical",
            )
            return False
        finally:
            self._active_lease_order_keys.discard(order_key)
            await self.tracker.release_lock(order_key)

    async def _get_current_regime(self) -> str:
        """
        Determine the current market regime from feature data.
        Falls back to 'ranging' if data is unavailable.
        """
        try:
            from sqlalchemy import text

            async with self.db.engine.connect() as conn:
                r = await conn.execute(
                    text("""
                    SELECT
                        symbol,
                        value AS rsi_14
                    FROM features
                    WHERE feature_name = 'rsi_14'
                    ORDER BY time DESC
                    LIMIT 1
                """)
                )
                row = r.fetchone()
                if row is not None:
                    rsi = float(row.rsi_14)
                    if rsi < 35:
                        return "oversold"
                    elif rsi > 65:
                        return "overbought"
                # Try volatility_regime for finer-grained detection
                r2 = await conn.execute(
                    text("""
                    SELECT value AS vol_regime
                    FROM features
                    WHERE feature_name = 'volatility_regime'
                    ORDER BY time DESC
                    LIMIT 1
                """)
                )
                vol_row = r2.fetchone()
                r3 = await conn.execute(
                    text("""
                    SELECT value AS ema_spread
                    FROM features
                    WHERE feature_name = 'ema_spread_pct'
                    ORDER BY time DESC
                    LIMIT 1
                """)
                )
                ema_row = r3.fetchone()

                vol = float(vol_row.vol_regime) if vol_row is not None else 1.0
                ema = float(ema_row.ema_spread) if ema_row is not None else 0.0

                if vol > 1.4:
                    return "high_volatility"
                elif abs(ema) > 0.003:
                    return "trending"
        except Exception as e:
            logger.debug(f"{self.name}: Regime detection failed: {e}")
        return "ranging"

    async def _refresh_scout_intelligence(self):
        """Refresh scout intelligence cache for dynamic adaptation."""
        import time

        now = time.time()
        if now - self._scout_cache_time < self._scout_cache_ttl:
            return
        try:
            scout = await self.db.get_latest_scout_intelligence()
            if not isinstance(scout, dict):
                return
            self._scout_liquidity_regime = scout.get("liquidity", {}).get("regime", "")
            self._scout_execution_regime = scout.get("execution", {}).get("regime", "")
            self._scout_cache_time = now
        except Exception:
            logger.debug(f"{self.name}: Scout refresh failed")

    def _scout_adjusted_qty(self, base_qty: float) -> float:
        """Reduce order size in stressed market conditions.

        Phase 26D: Also reduces sizing based on entropy when available.
        Phase 30: Less aggressive reduction to maintain trade density.
        """
        adjusted = base_qty
        if self._scout_liquidity_regime == "thin":
            adjusted *= 0.75  # Previously 0.5
        if self._scout_execution_regime in ("degraded", "stressed"):
            adjusted *= 0.85  # Previously 0.75
        if self._scout_execution_regime == "unstable":
            adjusted *= 0.50  # Previously 0.25
        # Phase 26D: Entropy-based sizing reduction (fetched from risk controller's state)
        try:
            entropy_val = (
                self.risk._scout_entropy
                if hasattr(self.risk, "_scout_entropy")
                else 0.0
            )
            if entropy_val > 0.7:
                adjusted *= 0.75  # Previously 0.5
            elif entropy_val > 0.5:
                adjusted *= 0.85  # Previously 0.75
        except Exception:
            pass
        return adjusted

    def _scout_adjusted_slippage(self) -> float:
        """Return widened slippage buffer in stressed conditions."""
        base_slippage = 10.0  # default 10 bps
        if self._scout_liquidity_regime == "thin":
            return base_slippage * 3.0
        if self._scout_execution_regime in ("degraded", "stressed"):
            return base_slippage * 2.0
        if self._scout_execution_regime == "unstable":
            return base_slippage * 5.0
        return base_slippage

    async def _submit_with_retry(
        self, client_order_id: str, symbol: str, side: str, qty: float, max_retries=3
    ) -> Optional[dict]:
        for attempt in range(max_retries):
            try:
                # By passing client_order_id, the broker handles idempotency on its end
                order = await self.broker.submit_order(
                    client_order_id=client_order_id, symbol=symbol, side=side, qty=qty
                )
                return order
            except Exception as e:
                logger.warning(f"Submit attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2**attempt)
        return None

    async def _poll_fill(self, broker_order_id: str, timeout: int = 30) -> dict:
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            try:
                status = await self.broker.get_order_status(broker_order_id)
                if status.get("status") in (
                    "filled",
                    "partially_filled",
                    "closed",
                    "cancelled",
                    "rejected",
                ):
                    return status
            except Exception as e:
                logger.debug(f"Poll error: {e}")
            await asyncio.sleep(2)
        return {"id": broker_order_id, "status": "timeout"}
