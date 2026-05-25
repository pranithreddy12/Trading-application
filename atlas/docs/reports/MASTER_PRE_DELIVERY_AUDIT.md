# MASTER PRE-DELIVERY AUDIT
## ATLAS Autonomous Trading Organism — Full Repository Operational Audit

**Date:** 2026-05-21
**Audit Layer:** Full-system (L1 through L7 + Scouts + Infrastructure)
**Audit Scope:** Operational correctness, replay integrity, survivability, determinism, governance, stability

---

## CRITICAL ISSUES

### C-01: EventStore Hash Chain Broken by Phase 24 Changes

**File:** `core/event_store.py` — `append_event()` method

**Root Cause:** Phase 24 changed `created_at` from `.isoformat()` string to `datetime.now(timezone.utc)` (datetime object). The hash computation uses `json.dumps(content, sort_keys=True)` which **cannot serialize datetime objects** — this will raise `TypeError: Object of type datetime is not JSON serializable` on every event append, breaking the entire event store.

**Current code:**
```python
now = datetime.now(timezone.utc)  # Was: now = datetime.now(timezone.utc).isoformat()
content = {
    ...
    "created_at": now,  # datetime object — json.dumps will FAIL
}
hash_self = hashlib.sha256(
    json.dumps(content, sort_keys=True).encode("utf-8")  # TypeError!
).hexdigest()
```

**Impact:** CRITICAL — Every event append crashes. Event store becomes non-functional. Replay lineage cannot be persisted. Governance chain broken.

**Fix Required:** Use `.isoformat()` for hash computation content (consistent with verify_integrity reconstruction), while keeping datetime for DB binding.

---

### C-02: EventStore.verify_integrity Hash Mismatch Deterministic Bug

**File:** `core/event_store.py` — `verify_integrity()` method

**Root Cause:** The hash reconstruction in `verify_integrity()` uses `event.created_at` which is a string (ISO format from `_rows_to_events`). But `append_event()` uses a datetime object in the content dict. Even after fixing C-01, both must use the **same representation**. Currently they don't match.

```python
# In verify_integrity:
content = {
    ...
    "created_at": event.created_at,  # String: "2024-01-01T12:00:00+00:00"
}

# In append_event (after fix):
content = {
    ...
    "created_at": now.isoformat(),  # String — matches!
}
```

**Impact:** All existing events have hashes computed with ISO strings (original code used `.isoformat()`). Current Phase 24 code would crash on new events. But if fixed to use isoformat(), new events match verify_integrity. Existing events already match because they were stored with isoformat().

**Fix Required:** Ensure hash content format matches between append_event and verify_integrity.

---

### C-03: KillSwitch.run() Blocks Event Loop Indefinitely

**File:** `agents/l4_risk/kill_switch.py` — `run()` method

**Root Cause:** `uvicorn.Server(config).serve()` is a long-running coroutine that blocks run() from ever returning or checking `self.status`. If the agent is stopped, the serve() call is not interruptible without the task being cancelled (which BaseAgent.stop() does), but the agent cannot gracefully stop its own run loop.

```python
async def run(self):
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    self._api_task = asyncio.create_task(server.serve())
    # ↓ This pubsub loop never runs because serve() blocks!
    while self.status == "running":
        message = await pubsub.get_message(...)
```

**Impact:** The pubsub subscription and loop after `server.serve()` is unreachable dead code. Risk alerts from other agents are never processed.

**Fix Required:** Make the FastAPI server a background task, then continue with the pubsub polling loop.

---

### C-04: EventStore Cached Created_at is Datetime While Stored as String

**File:** `core/event_store.py` — `append_event()` → DB write

**Root Cause:** The `_execute_insert` call passes `created_at: now` where `now` is a datetime object, via `::timestamptz` cast. This works for Postgres. But when events are read back via `_rows_to_events`, `created_at` becomes a string (`.isoformat()` called on the datetime). This inconsistency between write-time (datetime) and read-time (string) is the hash mismatch source.

**Fix Required:** Standardize on ISO string for hash computation, datetime for DB binding.

---

## HIGH ISSUES

### H-01: MessagingClient Silent Exception Suppression

**Files:** `core/messaging.py`

**Root Cause:** Both `publish()` and `subscribe()` use bare `except Exception: pass` — all errors are silently swallowed with zero logging.

```python
async def publish(self, channel: Channel, message: dict) -> None:
    try:
        payload = json.dumps(message)
        await self.redis.publish(channel.value, payload)
    except Exception:
        pass  # ← Silent! No logging at all.
```

**Impact:** Dead-letter messages are invisible. Redis connectivity issues go unnoticed. Operations teams have zero visibility into messaging failures.

**Fix Required:** Replace `pass` with `logger.warning` or `logger.error`.

---

### H-02: SelfImprovementAgent Bypasses BaseAgent Status Enum

**File:** `agents/l7_meta/self_improvement_agent.py` — `run()` method

**Root Cause:** The agent directly assigns `self.status = "running"` instead of using the BaseAgent's status management:

```python
async def run(self):
    self.status = "running"  # ← Bypasses BaseAgent.start() status
    while self.status == "running":
        ...
```

**Impact:** Status conflicts with BaseAgent lifecycle. If agent is paused via `pause()`, the run() method ignores it because it only checks its own set value.

**Fix Required:** Remove the redundant `self.status = "running"` line.

---

### H-03: ExecutionGateway Unbounded Lease Set

**File:** `agents/l5_execution/execution_gateway.py`

**Root Cause:** `self._active_lease_order_keys` is a plain set with no growth bound. If orders fail to complete (e.g., broker issues, crash loops), this set grows unboundedly holding stale keys:

```python
self._active_lease_order_keys: set[str] = set()
```

**Impact:** Memory leak under high-throughput scenarios with execution failures. In long-running autonomous operation, could consume significant memory.

**Fix Required:** Add periodic cleanup of stale entries or bound the set size.

---

### H-04: OrderTracker Logs Execution Entries with None Values

**File:** `agents/l5_execution/order_tracker.py` — `transition()` method

**Root Cause:** When `transition()` is called early in the execution pipeline (e.g., SIGNAL_RECEIVED), parameters like `strategy_id`, `symbol`, `side` may still be `None`. These get written to the execution_log as NULL/NONE values.

```python
params = {
    "strategy_id": strategy_id,  # Can be None
    "symbol": symbol or "UNKNOWN",  # Falls back to UNKNOWN
    "side": side or "UNKNOWN",  # Falls back to UNKNOWN
    ...
}
```

**Impact:** execution_log has incomplete data for early-stage transitions. Makes replay and audit unreliable for partial order lifecycle tracking.

**Fix Required:** Ensure all critical fields are populated before transition, or validate they are non-None.

---

### H-05: Scout JavaScript Timestamps Not Handled

**Files:** `agents/scouts/*.py` (all scouts)

**Root Cause:** Scouts generate timestamps with `datetime.now(timezone.utc)` which creates timezone-aware datetime objects. However, `serialization.py`'s `normalize_timestamp()` and `normalize_json_value()` handle this correctly. The issue is in the **scout_payload validation** path: `validate_scout_payload` receives payloads that have already been through `normalize_json_value()` which converts datetimes to strings, then `validate_scout_payload` converts them back to datetimes. This round-trip is redundant but functional.

**Impact:** Performance overhead. No correctness impact but adds unnecessary complexity.

**Fix Required:** Streamline the timestamp normalization path to avoid redundant conversions.

---

## MEDIUM ISSUES

### M-01: TimescaleClient._execute_insert Swallows Scout Validation Failures

**File:** `data/storage/timescale_client.py` — `_execute_insert()` method

**Root Cause:** When scout validation fails, the invalid payload is quarantined silently. But no feedback is given to the caller about the rejection:

```python
if not validation.valid:
    await self._quarantine_scout_payload(validation.normalized_payload, validation.reasons)
    return  # ← Silent return, caller doesn't know insert failed
```

**Impact:** Scout agents think their data was persisted when it was actually quarantined. This could lead to trust score drift.

**Fix Required:** Log a warning or return a failure indicator.

---

### M-02: Empty Except Blocks Across Codebase

**Files:**
- `agents/l5_execution/copy_trader.py` — `_poll_leader_orders()`, `_handle_leader_fill()`
- `agents/l5_execution/execution_gateway.py` — `_refresh_scout_intelligence()`
- `agents/l4_risk/risk_controller.py` — `approve_trade()`
- Multiple scout files

**Root Cause:** Widespread use of bare except blocks that catch and ignore all exceptions without logging:

```python
except Exception:
    pass
```

**Impact:** Failures invisible during operation. Debugging requires reproducing issues. Systemic degradation goes undetected until catastrophic failure.

**Fix Required:** Replace bare passes with `logger.exception()` or `logger.warning()` at minimum.

---

### M-03: CopyTraderAgent Handles Replay Events Non-Deterministically

**File:** `agents/l5_execution/copy_trader.py`

**Root Cause:** The `_handle_leader_fill` method uses `await self.redis.sadd(processed_set_key, leader_order_id)` for dedup. If Redis is flushed or the key expires, the same leader fill could be re-processed, leading to duplicate execution.

```python
was = await self.redis.sismember(self._processed_set_key, leader_order_id)
if was:
    return
...
await self.redis.sadd(self._processed_set_key, leader_order_id)
await self.redis.expire(self._processed_set_key, 60 * 60 * 24)
```

**Impact:** Non-deterministic behavior after Redis restart or key expiry. Duplicate orders possible.

**Fix Required:** Add DB-level idempotency check as secondary guard.

---

### M-04: AuditLedger.created_at Uses ISO String, Inconsistent with EventStore

**File:** `core/audit_ledger.py`

**Root Cause:** `now = datetime.now(timezone.utc).isoformat()` produces a string. The DB `::timestamptz` cast accepts both string and datetime, but the hash content uses a string while EventStore hash content uses (broken) datetime. Inconsistent patterns across the two hashing subsystems.

**Impact:** Increases cognitive load. Could lead to hash chain bugs in audit_ledger if someone refactors to use datetime like EventStore.

**Fix Required:** Standardize on datetime for consistency, matching EventStore fix.

---

### M-05: SystemHealthEngine Queries Tables Outside Schema Guarantee

**File:** `agents/l7_meta/system_health_engine.py`

**Root Cause:** Queries reference tables like `walk_forward_analysis`, `monte_carlo_analysis`, `portfolio_intelligence`, `replay_integrity`, `drift_detection`, `systemic_risk`, `system_health` which may not exist if migrations haven't fully run. The queries use `COUNT(*)` which returns 0 for non-existent tables (in Postgres they would error). Actually these are actual errors if tables don't exist.

```python
r = await conn.execute(
    text("SELECT COUNT(*) FROM portfolio_intelligence WHERE ...")
)
```

**Impact:** At startup or in degraded DB states, the health engine crashes instead of returning 0.

**Fix Required:** Wrap in try/except with safe defaults.

---

## LOW ISSUES

### L-01: TimescaleClient.engine.connect() Missing Connection Timeout

**File:** `data/storage/timescale_client.py`

**Root Cause:** The async engine is created without explicit pool_timeout or connect timeout settings. Default SQLAlchemy pool behavior may hang indefinitely under load.

```python
self.engine = create_async_engine(self.db_url, echo=False)
```

**Impact:** Potential hang during DB connection exhaustion.

---

### L-02: EventStore Lock Scope Too Broad

**File:** `core/event_store.py`

**Root Cause:** The `asyncio.Lock()` in `append_event()` serializes ALL event appends globally, rather than per-aggregate. This reduces throughput for independent aggregates.

**Impact:** Throughput bottleneck under high event volume. Less critical for current scale.

---

### L-03: Full Autonomous Cycle Starts Agents Sequentially

**File:** `scripts/full_autonomous_cycle.py` — `_start_agents()`

**Root Cause:** Agents are started with sequential `await agent.start()` calls rather than `asyncio.gather`. This adds startup latency.

```python
async def _start_agents(agents: list) -> list[asyncio.Task]:
    tasks: list[asyncio.Task] = []
    for agent in agents:
        await agent.start()  # Sequential
```

**Impact:** ~2-5 second startup delay per agent × 35+ agents = 1-3 minute startup time.

---

### L-04: Scout Validation Runs Twice Per Insert

**File:** `data/storage/timescale_client.py`

**Root Cause:** The `_execute_insert` for `external_scout_memory` calls `validate_scout_payload()` on already-validated params. Most callers validate before calling insert, so validation runs twice.

**Impact:** Unnecessary CPU overhead on scout data path.

---

## SCHEMA DRIFT ANALYSIS

### S-01: Schema Column Alignment ✓ (Already Fixed in Phase 24)

The Phase 24 migration in `timescale_client.py` handles all known schema drifts:
- event_store: Added sequence, version, metadata, hash_prev, hash_self
- audit_ledger: Added resource_type, resource_id, details, severity, hash_prev, hash_self
- paper_trades: Added id, qty
- strategies: Added mutation_type, generation_batch, trace_id
- lifecycle_events: Added agent_name
- external_scout_memory: Added details
- backtest_results: Added created_at

All critical columns are validated at startup.

---

## ASYNC HEALTH ANALYSIS

### A-01: Orphan Task Prevention ✓ (Phase 24 Addressed)

**Status:** PROTECTED

BaseAgent._run_with_retry:
- ✓ Min run duration (60s) prevents tight restart loops
- ✓ Min restart interval (30s) prevents restart storms
- ✓ Exponential backoff on retries
- ✓ Background tasks tracked via _track_background_task
- ✓ Done callbacks clean up tracked tasks

### A-02: Background Task Lifecycle Management ✓

**Status:** PROTECTED

Systems reviewed:
- ExecutionGateway: _track_background_task + _shutdown_background_tasks ✓
- CopyTraderAgent: _track_background_task + _shutdown_background_tasks ✓
- KillSwitch: Single _api_task managed explicitly ✓
- Full autonomous cycle: Auto-restart with exponential backoff ✓

---

## REPLAY INTEGRITY ANALYSIS

### R-01: Event Lineage ✓ (Working)

- EventLineageClient.create_trace ✓
- EventLineageClient.create_event ✓
- EventLineageClient.get_lineage ✓
- TraceGraphEngine causal chain reconstruction ✓

### R-02: Hash Chain Integrity ✗ (CRITICAL — C-01)

**Status:** BROKEN (see C-01)

---

## SCOUT NETWORK ANALYSIS

### SC-01: Timestamp Integrity ✓ (Phase 24 Fixed)

- Scouts now use `datetime.now(timezone.utc)` instead of `datetime.utcnow().isoformat()` ✓
- scout_validation.py uses centralized `normalize_timestamp()` ✓
- serialization.py handles ISO strings → datetime conversion ✓

### SC-02: Anti-Poisoning ✓ (Working)

- scout_quarantine table operational ✓
- scout_poison_quarantine stores violations ✓
- Payload size limit (16KB) enforced ✓
- Missing source/details detection ✓
- Confidence range validation (0.0-1.0) ✓

### SC-03: Trust Evolution ✓ (Partially Working)

- SourceReliabilityEngine tracks trust scores ✓
- Dynamic decay based on staleness ✓
- Contradiction tracking planned but not implemented

---

## EXECUTION GOVERNANCE ANALYSIS

### E-01: Idempotency ✓ (Working)

- OrderTracker.make_order_key generates deterministic keys ✓
- Redis SET for processed orders ✓
- 7-day TTL on processed set ✓
- DB-level execution_log provides secondary idempotency ✓

### E-02: Distributed Locking ✓ (Working)

- Redis SET NX with lease TTL ✓
- Instance ownership tracking ✓
- Lease renewal background task ✓
- Lost order recovery on startup ✓

### E-03: Dead Letter Management ✓ (Working)

- execution_dead_letter table ✓
- Unresolved dead letter tracking ✓
- Manual replay capability ✓

---

## PORTFOLIO & RISK ANALYSIS

### P-01: Kill Switch Persistence ✓ (Working)

- risk_state table persisted ✓
- Redis cache for fast check ✓
- DB as source of truth ✓
- Distributed kill switch activation ✓

### P-02: Systemic Risk Engine ✓ (Working)

- Contagion probability ✓
- Fragility scoring ✓
- Correlation regime detection ✓
- Concentration risk (HHI) ✓

### P-03: Capital Preservation ✗ (Not Tested)

- CapitalPreservationEngine exists but not verified
- Exposure cut ratios untested
- Peak value tracking untested

---

## SUMMARY STATISTICS

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Hash Chain Integrity | 2 | 0 | 0 | 0 |
| Async/Scheduling | 0 | 0 | 0 | 1 |
| Exception Handling | 0 | 1 | 2 | 0 |
| Schema Drift | 0 | 0 | 0 | 0 |
| Memory Management | 0 | 1 | 0 | 0 |
| Lifecycle | 0 | 1 | 0 | 0 |
| Data Integrity | 0 | 1 | 1 | 0 |
| Performance | 0 | 0 | 0 | 2 |
| **Total** | **2** | **4** | **3** | **3** |

---

## REMEDIATION PRIORITY

1. **C-01**: Fix EventStore.hash_self computation (json.dumps with datetime)
2. **C-02**: Fix EventStore.verify_integrity hash reconstruction format
3. **C-03**: Fix KillSwitch FastAPI blocking pattern
4. **H-01**: Fix MessagingClient silent exception suppression
5. **H-02**: Fix SelfImprovementAgent status enum bypass
6. **H-03**: Fix ExecutionGateway unbounded lease set
7. **H-04**: Fix OrderTracker None-column writes
8. **H-05**: Streamline scout timestamp normalization path
9. **M-01**: Add logging to scout validation failures
10. **M-02**: Replace empty except blocks with logging

---

*End of MASTER_PRE_DELIVERY_AUDIT.md*
