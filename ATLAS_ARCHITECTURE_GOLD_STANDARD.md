# ATLAS ARCHITECTURAL GOLD STANDARD

**Effective:** May 16, 2026 (Post-Day 4)  
**Status:** Platform Mandate (All Future Development)  
**Scope:** Every new system from this point forward

---

## MASTER PRINCIPLE

```
"Build simple where possible, but never fragile."
```

**This means:**
- ✅ Correct foundations before features
- ✅ Clean interfaces before optimization
- ✅ Security boundaries before scale
- ✅ Upgrade paths before complexity
- ✅ Operational resilience before sophistication

---

## ARCHITECTURE PRIORITY STACK (ALWAYS)

```
Tier 1: Data Integrity
        └─ Correct state at all times

Tier 2: Security
        └─ Authentication, RBAC, audit trails

Tier 3: Idempotency
        └─ Safe restart, crash recovery, replay

Tier 4: Observability
        └─ Health, metrics, lineage, failure reason

Tier 5: Control
        └─ API surface, governance, manual override

Tier 6: Scale
        └─ Distribution, concurrency, load handling

Tier 7: UX
        └─ Dashboards, flows, ergonomics

---

⚠️  IF UX COMES BEFORE FOUNDATION:
    You build → "Beautiful instability"
```

**Critical Rule:** Every feature moves up this stack in order, never skipping.

---

## 12 CORE ARCHITECTURAL PRINCIPLES

### 1. DOMAIN-DRIVEN MODULE BOUNDARIES

**Layers must remain clean:**

```
L1: Data Ingestion      (Binance, Polygon, etc.)
L2: Strategy Generation (Ideator, LLM, template)
L3: Validation         (Backtester, validator)
L4: Risk              (Risk checks, limits)
L5: Execution         (Copy trader, orders)
━━━━━━━━━━━━━━━━━━━━━
API: Control Plane    (Interface only)
Dashboard: Presentation (Visualization only)
Core: Services        (Business logic)
DB: State             (Source of truth)
```

**Rule:**
```
Never let Dashboard/API directly mutate Core systems.

BAD:   Dashboard → Direct DB writes
GOOD:  Dashboard → Auth API → Service → DB
```

**Benefit:** Clean separation means you can replace any layer without breaking others.

---

### 2. SERVICE ABSTRACTION OVER DIRECT COUPLING

**Reusable service layer:**

```python
class AuthService:
    async def verify_api_key(token: str) -> APIKeyRecord
    async def get_user_roles(key_id: str) -> List[Role]
    async def audit_log(action: str, user_id: str, resource_id: str)

class CopyService:
    async def execute_copy(leader_order_id: str, follower_id: str)
    async def calculate_allocation(ratio: float, leader_qty: int) -> int
    async def log_copy(order_id: str, status: str, latency_ms: int)

class RiskService:
    async def check_position_limit(follower_id: str, symbol: str, qty: int)
    async def check_daily_loss(follower_id: str, loss_pct: float)
    async def get_risk_metrics(follower_id: str)

class HealthService:
    async def check_database()
    async def check_redis()
    async def check_copy_trader()
    async def get_overall_status()
```

**Rule:**
```
APIs call services, NOT business rules inline.

Without this:
  API logic becomes duplicated system logic
  = Maintenance nightmare + drift
```

**Benefit:** Logic lives in one place. APIs are thin routing layers.

---

### 3. EVENT-FIRST THINKING

**ATLAS should increasingly behave as:**
```
State Machine + Event Bus + Audit Trail
```

**Core events to capture:**

```
StrategyGenerated(strategy_id, prompt, model_used, token_count)
StrategyValidated(strategy_id, train_sharpe, test_sharpe, status)
StrategyFailed(strategy_id, reason, backtest_error)

LeaderOrderCreated(order_id, leader_id, symbol, qty, price)
LeaderOrderFilled(order_id, filled_qty, fill_price, latency_ms)

CopyExecuted(copy_id, leader_order_id, follower_id, qty, latency_ms)
CopyFailed(copy_id, reason, error_code)
CopySkipped(copy_id, reason)

RiskCheckTriggered(follower_id, check_type, limit, current)
RiskCheckFailed(follower_id, check_type, limit, current)
KillSwitchActivated(follower_id, reason, timestamp)

APIKeyCreated(key_id, user_id, roles)
APIKeyRevoked(key_id, reason, revoked_by)
APIAccessAttempted(key_id, endpoint, status, latency_ms)
```

**Rule:**
```
Every important state change = Event

Event = (entity_type, action, data, timestamp, actor, reason)
```

**Why:**
- ✅ Complete audit trail
- ✅ Replayability (debug by replaying events)
- ✅ Future distributed scale
- ✅ Institutional memory
- ✅ Compliance ready

---

### 4. STATEFUL STATUS DESIGN

**Every major object has explicit lifecycle:**

```python
# Strategy Lifecycle
class StrategyStatus(str, Enum):
    draft              # Created, not yet validated
    validating         # Backtest in progress
    validated          # Passed validation, ready
    paused             # Temporarily disabled
    archived           # No longer active
    failed             # Validation error

# Order Lifecycle
class OrderStatus(str, Enum):
    pending            # Awaiting execution
    submitted          # Sent to broker
    filled             # Fully filled
    partial            # Partially filled
    rejected           # Broker rejected
    cancelled          # User cancelled
    error              # System error

# Copy Lifecycle
class CopyStatus(str, Enum):
    pending            # Awaiting execution
    executing          # In progress
    filled             # Successfully copied
    skipped            # Risk check failed
    error              # System error

# API Key Lifecycle
class APIKeyStatus(str, Enum):
    active             # Can be used
    paused             # Temporarily disabled
    revoked            # Permanently disabled
    expired            # Time-based expiry
```

**Rule:**
```
Never:  Ambiguous booleans only
        (is_active, can_trade, enabled...)

Use:    Explicit state machine
        (pending, active, paused, failed, archived)
```

**Benefit:**
- ✅ Explicit state transitions
- ✅ Debugging ("why is this stuck in 'validating'?")
- ✅ Analytics ("what % reach 'validated'?")
- ✅ Governance ("can we retire 'draft' strategies?")

---

### 5. SECURITY ARCHITECTURE (MANDATORY)

**MUST have:**
```
✓ Key hashing               (never store plaintext)
✓ RBAC framework           (role-based access control)
✓ Rate limiting            (per API key, per role)
✓ Endpoint scopes          (which endpoints per role)
✓ Audit logging            (every sensitive action)
✓ Token expiry             (no permanent credentials)
✓ Secret rotation          (ability to change secrets)
```

**SHOULD have:**
```
✓ Service account separation  (admin vs trader vs monitor)
✓ Admin action double-confirmation
✓ Sensitive action logging   (who, when, what, why)
✓ Rate limit alerts
```

**NEVER:**
```
✗ Single shared super-token long-term
✗ Hardcoded API keys in code
✗ Unencrypted passwords
✗ Admin access without audit trail
✗ Unauthenticated mutation endpoints
```

**Day 5 Implementation:**
```python
# API Key Table
table api_keys:
  id: UUID
  key_hash: str (bcrypt)
  user_id: UUID (foreign key)
  team_id: UUID (optional)
  roles: List[Role] (admin, trader, read_only, follower, monitor)
  scopes: List[str] (optional endpoint restrictions)
  is_active: bool
  created_at: datetime
  expires_at: datetime (optional, None = no expiry)
  last_used_at: datetime
  created_by: UUID
  revoked_at: datetime (soft delete)
  revoke_reason: str

# Audit Log Table
table audit_logs:
  id: UUID
  timestamp: datetime
  api_key_id: UUID (foreign key)
  user_id: UUID
  action: str (copy_order, create_follower, delete_key, etc.)
  resource_type: str (strategy, follower, order, etc.)
  resource_id: UUID
  status: str (success, failure, denied)
  status_code: int
  latency_ms: int
  error_reason: str (if failed)
  ip_address: str
```

---

### 6. DATABASE PHILOSOPHY

**Schema discipline = Strong architecture**

**ALWAYS:**
```
✓ Idempotent migrations    (IF NOT EXISTS, ADD COLUMN IF NOT EXISTS)
✓ Versioned SQL            (migrations/001_*, 002_*, etc.)
✓ Audit columns            (created_at, updated_at, created_by)
✓ Soft deletes where meaningful
✓ Indexes on foreign keys
✓ Comments on non-obvious columns
```

**PREFER:**
```
✓ JSONB for evolving metadata      (validation_metrics, config)
✓ Typed columns for deterministic  (sharpe, latency_ms, balance)
✓ Enums for fixed states           (status, role, action_type)
✓ Timestamps with timezone
```

**AVOID:**
```
✗ Ambiguous null semantics
✗ Bare booleans for state
✗ No audit trail
✗ Hardcoded IDs
✗ Circular dependencies
```

**Example (Good):**
```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY,
    
    -- Core deterministic data
    strategy_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES api_keys(id),
    
    -- State machine
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
      CHECK (status IN ('draft', 'validating', 'validated', 'paused', 'archived', 'failed')),
    
    -- Metrics (typed for analytics)
    train_sharpe NUMERIC(10,4),
    test_sharpe NUMERIC(10,4),
    holdout_sharpe NUMERIC(10,4),
    stability_score NUMERIC(5,4),
    overfit_flag BOOLEAN DEFAULT false,
    
    -- Evolving metadata (JSONB for flexibility)
    validation_metrics JSONB,          -- {'config': {...}, 'results': {...}}
    strategy_code JSONB,               -- {'prompts': [...], 'models': [...]}
    
    -- Audit trail
    updated_at TIMESTAMP WITH TIME ZONE,
    updated_by UUID REFERENCES api_keys(id),
    archived_at TIMESTAMP WITH TIME ZONE,
    archived_by UUID REFERENCES api_keys(id),
    archive_reason VARCHAR(500),
    
    -- Indexes
    INDEX idx_created_at ON strategies(created_at),
    INDEX idx_status ON strategies(status),
    INDEX idx_created_by ON strategies(created_by)
);
```

---

### 7. IDEMPOTENCY EVERYWHERE

**Critical question for every mutation:**
```
"If this process crashes and restarts, can it safely resume?"

If NO → Architecturally weak
```

**Pattern:**

```python
# Before: Sequential + fragile
async def copy_order(leader_order_id, follower_id):
    # If this crashes between steps, partially applied
    follower = get_follower(follower_id)
    qty = calculate_qty(follower.ratio, leader_qty)
    place_order(...)            # ← crash here?
    log_copy(...)               # ← never reaches

# After: Idempotent + safe
async def copy_order(leader_order_id, follower_id):
    # Step 1: Check if already copied (idempotency guard)
    existing = await db.query(
        "SELECT * FROM copy_execution_log "
        "WHERE leader_order_id = ? AND follower_id = ? "
        "AND status IN ('filled', 'skipped')"
    )
    if existing:
        return existing  # Already done, safe resume
    
    # Step 2: Calculate (pure function, no side effects)
    follower = await get_follower(follower_id)
    qty = calculate_qty(follower.ratio, leader_qty)
    
    # Step 3: Execute with atomic logging
    async with db.transaction():
        # Record in DB atomically
        copy_record = await db.insert(
            "copy_execution_log",
            leader_order_id=leader_order_id,
            follower_id=follower_id,
            qty=qty,
            status='pending'
        )
        
        # Execute order
        result = await place_order(qty)
        
        # Update status atomically
        await db.update(
            "copy_execution_log",
            where={"id": copy_record.id},
            status=result.status,
            latency_ms=result.latency_ms
        )
    
    # Step 4: Cache result (Redis)
    await redis.set(
        f"copy:processed:{leader_order_id}:{follower_id}",
        copy_record.id,
        ex=86400  # 24h
    )
    
    return copy_record
```

**Idempotency Patterns:**
```
✓ Check existence before insert
✓ Atomic DB transactions
✓ Redis cache for deduplication
✓ Unique constraints on (entity_id, action_id) pairs
✓ Event-based replay (if crashed, replay events in order)
✓ Graceful resume (WHERE NOT EXISTS checks)
```

---

### 8. OBSERVABILITY BY DESIGN

**Every subsystem must expose:**

```
✓ Health             (alive? responsive?)
✓ Throughput         (requests/sec, copies/min)
✓ Latency           (p50, p99, p99.9)
✓ Failures          (error count, error types)
✓ Last heartbeat    (age of last update)
✓ State             (running, paused, error)
```

**Endpoints:**

```
GET /health
  → Comprehensive system status
  → Checks: DB, Redis, copy_trader, validator, API
  → Status: healthy, degraded, critical

GET /metrics
  → Prometheus-style metrics
  → copy_orders_total, copy_latency_ms, api_requests_total, etc.

GET /copy/status
  → Current subsystem state (not historical)
  → Active followers, leaders, last copy latency

GET /status
  → Full operational snapshot
  → All subsystems, all metrics
```

**Example:**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-16T14:23:41Z",
  "subsystems": {
    "database": {
      "status": "healthy",
      "latency_ms": 5,
      "connections": 3,
      "pool_size": 10
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1,
      "keys": 142,
      "memory_mb": 25
    },
    "copy_trader": {
      "status": "running",
      "uptime_seconds": 3847,
      "leaders": 1,
      "followers": 1,
      "copies_per_minute": 0.2,
      "last_copy_latency_ms": 97,
      "last_heartbeat_seconds_ago": 1
    },
    "validator": {
      "status": "idle",
      "uptime_seconds": 8942,
      "last_validation_at": "2026-05-16T14:15:23Z",
      "validations_today": 3
    },
    "api": {
      "status": "healthy",
      "uptime_seconds": 892,
      "requests_per_minute": 12,
      "errors_per_minute": 0,
      "avg_latency_ms": 45
    }
  },
  "metrics": {
    "strategies_total": 42,
    "strategies_validated": 12,
    "copy_executions_total": 487,
    "api_key_count": 3
  }
}
```

---

### 9. CONFIGURATION DISCIPLINE

**Separate concerns:**

```
✓ Code              (github)
✓ Secrets           (.env, vault)
✓ Environment       (dev, staging, prod)
✓ Runtime flags     (feature gates)
```

**Never:**
```
✗ Hardcoded production assumptions
✗ API keys in code
✗ Environment-specific logic inline
✗ Magic strings/numbers
```

**Use:**

```python
# settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TOKEN: str = "atlas_day4_shared_token"  # From .env
    
    # Database
    DATABASE_URL: str  # From .env
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"  # From .env
    
    # Copy Trading
    COPY_POLLING_INTERVAL_SEC: float = 1.0
    COPY_MAX_ALLOCATION_PCT: float = 0.9
    
    # Risk
    MAX_POSITION_PCT: float = 0.05
    MAX_DAILY_LOSS_PCT: float = 0.02
    
    # Feature Flags
    ENABLE_REDIS_SUBSCRIBE: bool = True
    ENABLE_POLLING_LOOP: bool = True
    ENABLE_RATE_LIMITING: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

### 10. TESTING PYRAMID

**Not all tests are equal:**

```
                ▲
               /|\
              / | \
             /  |  \
            / E2E \ 
           /      |
          /───────┼─────\
         / Contract     \
        /  Tests        |
       /────────────────┼─────\
      /  Integration             \
     /    Tests                  |
    /──────────────────────────────\
   /          Unit Tests            \
  /__________________________________\
```

**REQUIRED at each level:**

```
Unit Tests:
  ✓ Individual functions
  ✓ Pure logic, mocked dependencies
  ✓ Fast (<10ms per test)

Integration Tests:
  ✓ Components + dependencies
  ✓ Real DB, real Redis (in-memory for tests)
  ✓ Service layer behavior

Smoke Tests:
  ✓ End-to-end critical path
  ✓ "Does copy trading work?"
  ✓ "Does API respond?"

Restart Tests:
  ✓ Crash & restart
  ✓ No duplicate execution
  ✓ Resume from saved state

Contract Tests:
  ✓ API count == DB count
  ✓ API filtering == DB query
  ✓ Prevent silent drift
```

**MOST MISSED (for ATLAS):**
```
Restart + Replay tests are CRITICAL

These catch:
  ✓ Incomplete transactions
  ✓ Lost state on crash
  ✓ Duplicate execution
  ✓ Silent data corruption
```

---

### 11. DASHBOARD PHILOSOPHY

**Dashboard is command center, NOT business engine**

**Dashboard SHOULD:**
```
✓ Display state (read from API)
✓ Trigger authorized actions (buttons → API calls)
✓ Show execution history
✓ Display risk warnings
✓ Monitor health
✓ Provide search/filter
```

**Dashboard SHOULD NOT:**
```
✗ Bypass services/APIs
✗ Write directly to DB
✗ Contain business logic
✗ Be the source of truth for anything
```

**Architecture:**
```
Dashboard
    │
    ├─→ REST API (read)
    │   └─→ Services
    │       └─→ DB
    │
    ├─→ REST API (write)
    │   └─→ Auth check
    │   └─→ Services
    │       └─→ DB
    │       └─→ Audit log
    │
    └─→ WebSocket (optional, for real-time)
        └─→ Health stream
        └─→ Execution stream
```

**Rule:**
```
If dashboard can do it, it goes through API.
If it bypasses API, it's architectural debt.
```

---

### 12. DESIGN FOR DAY 10, NOT JUST DAY 5

**Ask for every design decision:**

```
"Will this still make sense when:
  □ 1,000 strategies?
  □ 500 followers?
  □ Multiple brokers?
  □ 100 concurrent users?
  □ 10x load?
  □ New requirements we haven't thought of?"

If NO → Refactor now.
```

**Examples:**

```
Day 5 Design:
  Global in-memory copy state
  Single polling loop
  Shared database connection

Day 10 Reality:
  1000s of active copies
  Multiple instances of copy trader
  Need distributed state + message queue

→ Refactor now to event bus + state machine

Day 5 Design:
  API responses with inline data
  No pagination
  All results returned at once

Day 10 Reality:
  100K strategies
  10K copy logs per hour
  API response > 10 seconds

→ Add pagination now
```

---

## QUALITY GATE CHECKLIST

**Before any feature ships, answer:**

### Data Integrity
```
✓ Can this data survive crashes?
✓ Are there integrity constraints?
✓ Does restart apply correctly?
✓ Are duplicates prevented?
```

### Security
```
✓ Is access scoped to authorized users?
✓ Is this action audited?
✓ Can this be rate-limited?
✓ Are secrets protected?
```

### Idempotency
```
✓ Can this operation safely resume?
✓ Are duplicate executions impossible?
✓ Is state saved before mutations?
```

### Observability
```
✓ Is success/failure visible?
✓ Is latency measurable?
✓ Can I see the full execution path?
✓ Are errors categorized?
```

### Maintainability
```
✓ Is this decoupled from other systems?
✓ Can this be tested independently?
✓ Is error handling clear?
✓ Would someone else understand this in 6 months?
```

### Scalability
```
✓ Will this design work at 10x load?
✓ Is there a bottleneck here?
✓ Are there connection limits?
✓ Is this horizontally scalable?
```

---

## GOLDEN QUESTION FOR EVERY NEW MODULE

```
"Does this improve trust, resilience, control, or scalability
 without compromising architecture?"

IF YES:    Proceed
IF NO:     Reconsider
IF MAYBE:  Architect first, build second
```

---

## DEVELOPMENT SEQUENCE (DAY 5+)

### PHASE A: Platform Hardening (Days 5-6)
```
✓ RBAC + API key management
✓ Rate limiting
✓ Health checks (deep)
✓ Audit logging
✓ Contract tests
```

### PHASE B: Service Extraction (Days 6-7)
```
✓ AuthService (from API logic)
✓ CopyService (from copy trader)
✓ RiskService (from risk checks)
✓ HealthService (from health checks)
```

### PHASE C: Operational Visibility (Days 7-8)
```
✓ Dashboard prototype
✓ Real-time metrics
✓ Execution log UI
✓ Status visualization
```

### PHASE D: Write Control Layer (Days 8-9)
```
✓ POST /copy/order
✓ POST /followers
✓ PUT /followers/{id}
✓ DELETE /followers/{id}
✓ Risk enforcement in writes
```

### PHASE E: Distributed Scale (Days 10+)
```
✓ Message queue (for copy distribution)
✓ Distributed state machine
✓ Multi-broker adapter
✓ Portfolio aggregation
```

---

## ARCHITECTURAL MISTAKES TO ABSOLUTELY AVOID

### ❌ MISTAKE 1: Feature-First Without Service Boundaries

```
WRONG:
  Add feature to API
  → API writes directly to DB
  → Copy trader also reads same tables
  → Logic duplicated, drift inevitable

RIGHT:
  Create Service
  → Service owns logic
  → API calls service
  → Copy trader calls service
  → One source of truth
```

---

### ❌ MISTAKE 2: Dashboard Tightly Coupled to DB

```
WRONG:
  Dashboard SQL query → Direct DB → Hardcoded assumptions
  DB schema changes → Dashboard breaks
  Copy trader can't find the data

RIGHT:
  Dashboard → REST API → Service → DB
  DB schema changes → API/service adapts
  Everyone sees consistent view
```

---

### ❌ MISTAKE 3: No Event Lineage

```
WRONG:
  Copy executed
  Log written
  No one knows what happened before/after
  Can't replay errors
  Can't audit

RIGHT:
  Event stream:
    StrategyGenerated → StrategyValidated → LeaderOrderCreated
    → LeaderOrderFilled → CopyExecuted → Success
  Can replay entire sequence
  Complete audit trail
  Can answer "why did this copy fail?"
```

---

### ❌ MISTAKE 4: Security Retrofitted Later

```
WRONG:
  Build all features with shared token
  Later: "Add RBAC"
  Have to refactor every endpoint

RIGHT:
  Build auth from Day 1
  Every feature scoped to authenticated user
  RBAC is natural extension
  No rework needed
```

---

### ❌ MISTAKE 5: Operational State Not Queryable

```
WRONG:
  Copy trader running internally
  No way to ask "what's the status?"
  Dashboard: "Is it working?" → Guess

RIGHT:
  `/health` endpoint answers all questions
  `/copy/status` shows real-time state
  `/metrics` shows throughput/latency
  Dashboard queries these
  Ops team can debug anything
```

---

## FINAL ATLAS ARCHITECTURE TARGET

```
ATLAS = Institutional Autonomous Trading Platform

Layer 7: Evolution
         (Strategy improvements, model refinement)

Layer 6: Control Plane
         (Write APIs, admin actions, governance)

Layer 5: Visibility
         (Dashboards, monitoring, analytics)

Layer 4: Security
         (RBAC, audit, rate limiting)

Layer 3: Execution Engine
         (Copy trader, orders, risk)

Layer 2: Validation Engine
         (Backtest, walk-forward, metrics)

Layer 1: Research Engine
         (Generation, ideation, strategy crafting)

Foundation: Data Layer
            (DB, Redis, event stream)
```

---

## STRONGEST PRACTICAL RULE

```
"Optimize for maintainability and trust first;
 sophistication compounds naturally on top of clean architecture."

Clean architecture beats clever features every time.
```

---

## SIGN-OFF: ARCHITECTURAL GOLD STANDARD

**Effective immediately:** Every module developed from this point forward must:

1. ✅ Have clear domain boundaries
2. ✅ Use service abstraction
3. ✅ Capture important events
4. ✅ Use explicit status lifecycle
5. ✅ Enforce security boundaries
6. ✅ Follow database discipline
7. ✅ Be idempotent and crash-safe
8. ✅ Expose operational health
9. ✅ Separate code/config/secrets
10. ✅ Pass full testing pyramid
11. ✅ Keep dashboards thin
12. ✅ Scale to Day 10 requirements

**Non-negotiable:** No shortcuts. No architectural debt. Build it right the first time.

---

**This is the foundation for ATLAS to become the platform you envision.**

**Generated:** May 16, 2026  
**Status:** Mandatory Architecture Standard ✅
