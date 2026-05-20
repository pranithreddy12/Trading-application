# ATLAS BEST-STRUCTURED ARCHITECTURE — ENFORCEMENT BLUEPRINT

**Date:** May 16, 2026  
**Status:** Mandatory Architecture Standard (All Future Work)  
**Scope:** Platform Operating System Design (10-Layer Structure)  
**Purpose:** Build institutional infrastructure, not tightly-coupled application code

---

## MASTER PRINCIPLE

```
"Prioritize architecture that reduces future complexity,
 not architecture that merely supports current functionality."

ATLAS should behave like modular institutional infrastructure:
  ✓ Each subsystem secure
  ✓ Each subsystem observable  
  ✓ Each subsystem independently testable
  ✓ Each subsystem replaceable
  ✓ Each subsystem scalable

This makes ATLAS progressively harder to break as it becomes more powerful.
```

---

## 10-LAYER BEST-STRUCTURED ARCHITECTURE

### LAYER 1: CORE DOMAIN ENGINES (KEEP PRISTINE)

**Scope:** `atlas/agents/` (L1-L7) + `atlas/core/` + `atlas/data/`

**Principle:**
```
Core engines should remain independently runnable without API or dashboard.
They are the platform's intellectual property.
```

**The 7 Layers:**

```
L1: Data Ingestion        (Binance, Polygon, market feeds)
    ├─ Protocols
    ├─ Adapters  
    └─ Connectors
    
L2: Strategy Research     (Ideation, generation, prompt engineering)
    ├─ Ideator (LLM-based)
    ├─ Templates
    └─ Mutation engine
    
L3: Validation           (Backtesting, walk-forward, holdout)
    ├─ Backtest runner
    ├─ Validator
    └─ Metrics
    
L4: Risk                 (Position limits, drawdown, leverage)
    ├─ Risk checks
    ├─ Kill switch
    └─ Alert system
    
L5: Execution           (Copy trading, order placement)
    ├─ Copy trader
    ├─ Order adapter
    └─ Position tracking
    
L6: [Reserved for Day 6+ analysis layer]

L7: Meta Intelligence    (Strategy evolution, learning)
    ├─ Performance analysis
    ├─ Adaptation
    └─ Reporting
```

**Design Rules:**

✅ **DO:**
```python
# Core engine standalone
class CopyTrader:
    async def execute_copy(self, leader_order, follower_id):
        # Pure trading logic, no API/auth knowledge
        # Can be tested independently
        # Can be deployed headless
        
# Core engine only talks to services it needs
async def __init__(self, db, risk_service, logging):
    self.db = db
    self.risk = risk_service
    self.logger = logging
```

❌ **DON'T:**
```python
# Core engine polluted with API/UI concerns
class CopyTrader:
    async def execute_copy(self, request: Request, api_key):
        if api_key.role != "trader":
            raise HTTPException(403)
        # Now core logic mixed with auth
        
# Core engine hardcodes dependencies
class CopyTrader:
    def __init__(self):
        self.db = PostgreSQL_connection  # Direct coupling
        self.redis = Redis_connection     # Tightly bound
```

**Benefit:**
- Easier testing (no need for API setup)
- Isolation (failure doesn't cascade)
- Failover (can run independently)
- Headless ops (cron jobs, CLI, etc.)

---

### LAYER 2: SERVICE ORCHESTRATION (BUSINESS LOGIC LAYER)

**Scope:** `atlas/api/services/`

**Principle:**
```
Business logic belongs here, NOT in endpoints.
Services are the governance layer.
```

**Required Services (Days 5-7):**

```
1. AuthService              ✅ DONE (Day 5 Phase A)
   ├─ API key generation
   ├─ RBAC enforcement
   ├─ Scope checking
   └─ Audit logging

2. RateLimitService        (Day 5 Phase A-2)
   ├─ Token bucket
   ├─ Per-key limiting
   └─ Rate limit headers

3. CopyService             (Day 5 Phase B)
   ├─ Execute copy logic
   ├─ Risk enforcement
   ├─ Idempotency
   └─ Latency tracking

4. RiskService             (Day 5 Phase B)
   ├─ Position limits
   ├─ Drawdown checks
   ├─ Kill switch
   └─ Alert generation

5. HealthService           (Day 5 Phase B)
   ├─ Subsystem checks
   ├─ Dependency status
   └─ Metrics aggregation

6. StrategyService         (Day 6)
   ├─ Strategy lifecycle
   ├─ Validation workflow
   └─ Lineage tracking

7. PortfolioService        (Day 6+)
   ├─ Position aggregation
   ├─ P&L calculation
   └─ Risk metrics

8. NotificationService     (Day 7)
   ├─ Webhook dispatch
   ├─ Email alerts
   └─ Slack integration
```

**Pattern (AuthService Template):**

```python
class CopyService:
    """
    Business logic for copy trading.
    
    Principles:
      - Independent of API/UI
      - All mutations audited
      - Idempotent operations
      - Observable failures
    """
    
    def __init__(self, db: TimescaleClient, risk_service: RiskService):
        self.db = db
        self.risk = risk_service
    
    async def execute_copy(self, leader_order_id: str, follower_id: str):
        """
        Execute copy with full audit trail and risk checks.
        
        Idempotency: Safe to call multiple times, no duplicates.
        """
        # 1. Check already executed (idempotency guard)
        existing = await self.db.query(
            "SELECT id FROM copy_execution_log WHERE leader_order_id = ? AND follower_id = ?"
        )
        if existing:
            return existing  # Already done
        
        # 2. Get follower config
        follower = await self.db.get_follower(follower_id)
        
        # 3. Calculate quantity
        qty = self._calculate_allocation(follower.ratio, leader_qty)
        
        # 4. Risk check (service abstraction)
        allowed = await self.risk.check_copy_allowed(follower_id, qty)
        if not allowed:
            await self._audit_log("copy_skipped", reason="Risk check failed")
            return None
        
        # 5. Execute atomically
        async with self.db.transaction():
            result = await self._place_order(qty)
            await self._log_copy(result)
            await self._audit_log("copy_executed", result)
        
        return result
    
    async def _audit_log(self, action: str, data: dict):
        """Immutable audit trail"""
        await self.db.insert("audit_logs", {
            "action": action,
            "timestamp": now(),
            "data": json(data)
        })
```

**Rule for Services:**

```
Service methods should answer:
  ✓ What business rule am I enforcing?
  ✓ How do I fail safely?
  ✓ What do I audit?
  ✓ Can I be called twice without duplicates?

If any answer is unclear → Refactor before shipping
```

---

### LAYER 3: MIDDLEWARE STACK (REQUEST GOVERNANCE)

**Scope:** `atlas/api/middleware/`

**Principle:**
```
Standardize request governance via composable middleware.
Order matters.
```

**Standard Pipeline:**

```
┌─────────────────┐
│ HTTP Request    │
└────────┬────────┘
         │
    ┌────▼──────────────────────┐
    │ 1. Logger Middleware       │ (Request ID, timestamp)
    │    Track: path, method     │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 2. Auth Middleware         │ (Verify Bearer token)
    │    Track: user, role       │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 3. RateLimit Middleware    │ (Token bucket per key)
    │    Track: key, remaining   │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 4. Validation Middleware   │ (Request schema validation)
    │    Track: errors           │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 5. Endpoint Router         │ (Invoke handler)
    │    → Service call          │
    │    → DB operation          │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 6. Response Middleware     │ (Build response)
    │    Track: latency          │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ 7. Audit Middleware        │ (Log to audit_logs)
    │    Track: action, status   │
    └────┬─────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ HTTP Response              │ (+ X-RateLimit-* headers)
    └─────────────────────────────┘
```

**Implementation Pattern:**

```python
# middleware/__init__.py
from .auth_middleware import AuthMiddleware, verify_token
from .rate_limit_middleware import RateLimitMiddleware, check_rate_limit
from .audit_middleware import AuditMiddleware, audit_request
from .validation_middleware import ValidationMiddleware, validate_request

# In main API file
app = FastAPI()

# Register middleware (order matters!)
app.add_middleware(LoggerMiddleware)      # 1st
app.add_middleware(AuthMiddleware)         # 2nd
app.add_middleware(RateLimitMiddleware)    # 3rd
app.add_middleware(ValidationMiddleware)   # 4th
app.add_middleware(AuditMiddleware)        # 5th (last, before endpoint)

@app.get("/copy/logs")
async def copy_logs(
    api_key = Depends(verify_token),      # Auth already verified
    # Validation already done
    # Rate limit already checked
):
    # Endpoint just calls service
    return await copy_service.get_logs(api_key.user_id)
```

---

### LAYER 4: EVENT + AUDIT ARCHITECTURE (PLATFORM MEMORY)

**Scope:** `atlas/data/` + All services

**Principle:**
```
Every meaningful mutation creates an immutable event.
This is the platform's memory and debugging trail.
```

**Event Types:**

```python
# Core domain events
class StrategyEvent:
    strategy_id: UUID
    action: str  # created, validated, failed, deployed, paused
    timestamp: datetime
    actor_id: str  # who triggered
    reason: str
    old_state: dict
    new_state: dict

# Execution events
class CopyEvent:
    copy_id: UUID
    action: str  # executed, skipped, failed
    leader_order_id: UUID
    follower_id: UUID
    qty: float
    status: str
    latency_ms: int

# Risk events
class RiskEvent:
    risk_id: UUID
    action: str  # check_triggered, limit_exceeded, kill_switch_activated
    follower_id: UUID
    check_type: str  # position_limit, daily_loss, leverage
    current_value: float
    limit_value: float

# API events
class APIEvent:
    action: str  # key_created, key_revoked, access_denied, rate_limited
    api_key_id: UUID
    endpoint: str
    status_code: int
```

**Tables:**

```sql
CREATE TABLE strategy_events (
    id UUID PRIMARY KEY,
    strategy_id UUID NOT NULL,
    action VARCHAR(50),
    timestamp TIMESTAMP WITH TIME ZONE,
    actor_id VARCHAR(100),
    reason VARCHAR(500),
    old_state JSONB,
    new_state JSONB,
    INDEX (strategy_id, timestamp DESC)
);

CREATE TABLE copy_events (
    id UUID PRIMARY KEY,
    copy_id UUID,
    leader_order_id UUID,
    follower_id UUID,
    action VARCHAR(50),
    status VARCHAR(20),
    qty FLOAT,
    latency_ms INT,
    timestamp TIMESTAMP WITH TIME ZONE,
    INDEX (follower_id, timestamp DESC),
    INDEX (leader_order_id)
);

CREATE TABLE risk_events (
    id UUID PRIMARY KEY,
    follower_id UUID,
    action VARCHAR(50),
    check_type VARCHAR(50),
    current_value FLOAT,
    limit_value FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE,
    INDEX (follower_id, timestamp DESC)
);

CREATE TABLE api_events (
    id UUID PRIMARY KEY,
    api_key_id UUID,
    action VARCHAR(50),
    endpoint VARCHAR(255),
    status_code INT,
    timestamp TIMESTAMP WITH TIME ZONE,
    INDEX (api_key_id, timestamp DESC),
    INDEX (action, timestamp DESC)
);
```

**Benefit:**
```
✓ Replay (what happened when?)
✓ Audit (who did what?)
✓ Debugging (trace execution path)
✓ Analytics (performance over time)
✓ Compliance (immutable record)
```

---

### LAYER 5: STATE MACHINES (OPERATIONAL CLARITY)

**Scope:** Every entity with lifecycle

**Principle:**
```
Replace boolean confusion with explicit states.
Every state transition is deliberate and auditable.
```

**Pattern:**

```python
# Strategy lifecycle
class StrategyStatus(str, Enum):
    DRAFT              # Created, not validated
    VALIDATING         # Backtest in progress
    VALIDATED          # Passed validation
    DEPLOYED           # Active in live trading
    PAUSED             # Temporarily disabled
    FAILED             # Validation error
    ARCHIVED           # No longer active

# Valid transitions (enforce in service)
VALID_TRANSITIONS = {
    DRAFT: [VALIDATING, ARCHIVED],
    VALIDATING: [VALIDATED, FAILED],
    VALIDATED: [DEPLOYED, PAUSED, FAILED],
    DEPLOYED: [PAUSED, FAILED],
    PAUSED: [DEPLOYED, FAILED],
    FAILED: [ARCHIVED],
    ARCHIVED: [],  # Terminal
}

class StrategyService:
    async def transition_status(self, strategy_id, new_status, reason):
        """Enforce state machine"""
        current = await self.get_status(strategy_id)
        
        if new_status not in VALID_TRANSITIONS[current]:
            raise ValueError(f"Invalid: {current} → {new_status}")
        
        async with self.db.transaction():
            await self.db.update_status(strategy_id, new_status)
            await self._audit_log("status_changed", {
                "from": current,
                "to": new_status,
                "reason": reason
            })
```

**Apply to:**
```
✓ API keys        (active → revoked → archived)
✓ Strategies      (draft → validating → validated → deployed)
✓ Followers       (active → paused → archived)
✓ Copy jobs       (pending → executing → filled → skipped)
✓ Orders          (pending → submitted → filled → rejected)
✓ Risk checks     (triggered → enforced → clear)
```

---

### LAYER 6: CONFIGURATION SYSTEM (SAFE OPERATIONS)

**Scope:** `atlas/config/` + `settings.py`

**Principle:**
```
Configuration enables safe deployments.
Never hardcode operational decisions.
```

**Levels:**

```python
# Level 1: Static config (.env file, deployed with code)
class Settings:
    DATABASE_URL: str
    REDIS_URL: str
    LOG_LEVEL: str
    API_PORT: int

# Level 2: Runtime config (DB table, changed without deploy)
class RuntimeConfig:
    """Queryable at runtime"""
    copy_trading_enabled: bool
    dashboard_write_enabled: bool
    kill_switch_force: bool
    rate_limit_override_user_ids: List[str]
    max_followers_per_leader: int

# Level 3: Feature flags (granular control)
class FeatureFlags:
    """Toggle features per environment"""
    enable_ideator_v2: bool
    enable_validator_walkforward: bool
    enable_copy_trading: bool
    enable_risk_checks: bool
    enable_api_write_endpoints: bool

# Query runtime config
async def should_execute_copy() -> bool:
    config = await get_runtime_config()
    return config.copy_trading_enabled  # Can disable without restart!

# Usage in services
class CopyService:
    async def execute(self, ...):
        if not await should_execute_copy():
            logger.info("Copy trading disabled via runtime config")
            return None
        # Proceed with execution
```

**Benefits:**
```
✓ Safer deployments (disable feature without redeploy)
✓ Controlled rollouts (enable for % of users)
✓ Emergency stops (kill_switch_force)
✓ A/B testing (feature_flags)
```

---

### LAYER 7: SCHEMA GOVERNANCE (DATABASE DISCIPLINE)

**Scope:** `scripts/migrations/`

**Principle:**
```
Strong schema enables strong architecture.
Every table tells a story.
```

**Migration Discipline:**

```sql
-- scripts/migrations/day5_example.sql (VERSIONED)

-- Idempotent: All operations use IF NOT EXISTS
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core data
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NOT NULL,
    
    -- Audit columns (ALWAYS include)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    updated_by VARCHAR(100),
    
    -- Soft delete
    archived_at TIMESTAMP WITH TIME ZONE,
    archive_reason VARCHAR(500),
    
    -- Constraints
    CONSTRAINT audit_events_valid_dates 
        CHECK (created_at <= updated_at OR updated_at IS NULL),
    CONSTRAINT audit_events_valid_archive 
        CHECK (created_at <= archived_at OR archived_at IS NULL)
);

-- Indexes (strategic, not random)
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at 
    ON audit_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_action 
    ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_events_resource 
    ON audit_events(resource_type, resource_id);

-- Documentation
COMMENT ON TABLE audit_events IS 'Immutable operation log for compliance';
COMMENT ON COLUMN audit_events.created_by IS 'Actor ID (API key or user)';
```

**Rules:**

```
✅ DO:
  - Idempotent (IF NOT EXISTS)
  - Versioned filenames (001_, 002_, etc.)
  - Audit columns (created_at, created_by, etc.)
  - Constraints (CHECK, FOREIGN KEY)
  - Indexes on hot queries
  - Comments (why, not what)
  - Soft deletes (archive_at marker)

❌ DON'T:
  - Manual raw SQL in code
  - Hardcoded IDs
  - Missing constraints
  - Unnecessary indexes
  - No rollback plan
  - Destructive operations without backup
```

**Schema Pattern:**

```sql
-- Core deterministic data: TYPED columns
id UUID PRIMARY KEY
name VARCHAR(255) NOT NULL
status VARCHAR(50) NOT NULL (ENUM)
train_sharpe NUMERIC(10,4)

-- Flexible metadata: JSONB
validation_metrics JSONB          -- {config, results, ...}
strategy_lineage JSONB            -- {parent, generation, ...}

-- Audit columns: ALWAYS
created_at TIMESTAMP WITH TIME ZONE
created_by VARCHAR(100)
updated_at TIMESTAMP WITH TIME ZONE
updated_by VARCHAR(100)
archived_at TIMESTAMP WITH TIME ZONE  -- Soft delete

-- Indexes: STRATEGIC
INDEX (created_at DESC)           -- For recent queries
INDEX (status)                    -- For filtering
INDEX (created_by)                -- For user queries
```

---

### LAYER 8: TESTING ARCHITECTURE (COMPREHENSIVE COVERAGE)

**Scope:** `scripts/tests/`

**Principle:**
```
Testing is not optional. It's how you verify the architecture works.
```

**Test Categories:**

```
Unit Tests (30%)
  └─ Service methods in isolation
    ├─ Key generation + hashing
    ├─ Business logic (pure functions)
    └─ Error handling
  
Integration Tests (40%)
  └─ Services + database
    ├─ CopyService with real DB
    ├─ RiskService with real constraints
    └─ Transactions + rollbacks
  
Contract Tests (15%)
  └─ API ↔ DB consistency
    ├─ GET /copy/logs count == DB count
    ├─ GET /followers filtered == DB query
    └─ Prevent silent drift
  
Smoke Tests (10%)
  └─ End-to-end critical path
    ├─ Generate strategy → validate → deploy
    ├─ Place leader order → mirror to follower
    └─ All systems operational

Restart Tests (5%)
  └─ Crash recovery
    ├─ Kill process mid-operation
    ├─ Restart and resume
    └─ No duplicates, no data loss

Security Tests
  └─ Invalid key, expired key, revoked key
  └─ Scope denial, rate limit, brute force
```

**Test Structure:**

```python
# scripts/tests/day5/test_copy_service.py

# UNIT: Service logic
@pytest.mark.asyncio
async def test_copy_calculation():
    """Pure logic, no DB"""
    service = CopyService(mock_db, mock_risk)
    qty = service._calculate_allocation(0.5, 100)
    assert qty == 50

# INTEGRATION: Service + DB
@pytest.mark.asyncio
async def test_copy_execution(test_db):
    """Real DB, transactional"""
    service = CopyService(test_db, mock_risk)
    result = await service.execute_copy(leader_id, follower_id)
    
    # Verify in DB
    log = await test_db.query("SELECT * FROM copy_execution_log WHERE id = ?", result.id)
    assert log.status == "filled"

# CONTRACT: API ↔ DB
@pytest.mark.asyncio
async def test_copy_logs_count_matches():
    """API and DB must agree"""
    api_count = len((await http_get("/copy/logs"))["data"])
    db_count = await db.scalar("SELECT COUNT(*) FROM copy_execution_log")
    assert api_count == db_count

# SMOKE: Critical path
@pytest.mark.asyncio
async def test_full_copy_flow():
    """Generate → validate → execute"""
    strategy = await create_strategy()
    await validate_strategy(strategy.id)
    order = await place_leader_order(strategy.id)
    copy = await execute_copy(order.id, follower_id)
    assert copy.status == "filled"

# RESTART: Crash recovery
@pytest.mark.asyncio
async def test_copy_idempotent():
    """Crash mid-execution, resume safely"""
    result1 = await service.execute_copy(leader_id, follower_id)
    # Simulate crash
    result2 = await service.execute_copy(leader_id, follower_id)  # Resume
    assert result1.id == result2.id  # Same copy, no duplicate
```

---

### LAYER 9: OBSERVABILITY SYSTEM (OPERATIONAL TRUTH)

**Scope:** All services + dashboard

**Principle:**
```
If you can't measure it, you can't operate it.
Every subsystem must expose health, metrics, and failures.
```

**Standard Health Pattern:**

```python
class HealthService:
    """Every subsystem health in one place"""
    
    async def check_database(self):
        try:
            result = await self.db.query("SELECT 1")
            return {"status": "healthy", "latency_ms": ...}
        except Exception as e:
            return {"status": "critical", "error": str(e)}
    
    async def check_copy_trader(self):
        try:
            heartbeat = await self.db.query(
                "SELECT MAX(created_at) FROM copy_execution_log"
            )
            if not heartbeat or age > 60:  # No copy in 60s
                return {"status": "warning", "age_seconds": age}
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "critical"}
    
    async def check_validator(self):
        # Similar pattern
    
    async def get_overall_status(self):
        """Aggregate: healthy | degraded | critical"""
        checks = [
            await self.check_database(),
            await self.check_copy_trader(),
            await self.check_validator(),
        ]
        
        status = "healthy"
        if any(c["status"] == "critical" for c in checks):
            status = "critical"
        elif any(c["status"] == "warning" for c in checks):
            status = "degraded"
        
        return {"status": status, "checks": checks}

# Expose via API
@app.get("/health")
async def health(health_service = Depends(get_health_service)):
    return await health_service.get_overall_status()

# Query in SQL (dashboard)
SELECT subsystem, status, last_check, latency_ms FROM health_checks;
```

**Metrics to Track:**

```
✓ Copy execution latency (p50, p99, p99.9)
✓ Strategy validation success rate
✓ Risk check frequency + blocks
✓ API request count + errors
✓ Database query latency
✓ Redis hit rate
✓ Subsystem uptime
```

---

### LAYER 10: DASHBOARD / CONTROL PLANE (LAST, NOT FIRST)

**Scope:** Frontend (React/Vue) + Dashboard APIs

**Principle:**
```
Build dashboard AFTER governance is solid.
Dashboard should NEVER bypass service boundaries.
```

**Pattern:**

```
Dashboard
    ↓
API Endpoints (authenticated, scoped)
    ↓
Middleware (auth, rate limit, audit)
    ↓
Services (business logic)
    ↓
Database (source of truth)

NOT:

Dashboard
    ↓
    ↓ (direct SQL query)
    ↓
Database  ❌ WRONG
```

**Dashboard Responsibilities:**

```
✓ Display state (read from API)
✓ Trigger actions (POST to API)
✓ Show alerts (from /health)
✓ Visualize metrics (from /metrics)
✓ Provide manual controls (kill switch, pause trader)

✗ Business logic
✗ Direct DB access
✗ Authentication bypass
✗ Security enforcement (done by API)
```

---

## BEST FILE STRUCTURE

```
atlas/
│
├── agents/                       ← CORE DOMAIN (L1-L7)
│   ├── l1_data/
│   ├── l2_strategy/
│   ├── l3_backtest/
│   ├── l4_risk/
│   ├── l5_execution/
│   └── l7_meta/
│
├── api/                          ← CONTROL PLANE
│   ├── middleware/               ← REQUEST GOVERNANCE (Layer 3)
│   │   ├── __init__.py
│   │   ├── auth_middleware.py
│   │   ├── rate_limit_middleware.py
│   │   ├── validation_middleware.py
│   │   └── audit_middleware.py
│   │
│   ├── services/                 ← BUSINESS LOGIC (Layer 2)
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── copy_service.py
│   │   ├── risk_service.py
│   │   ├── health_service.py
│   │   └── strategy_service.py
│   │
│   └── routes/                   ← THIN CONTROLLERS
│       ├── __init__.py
│       ├── copy_routes.py
│       ├── strategy_routes.py
│       └── health_routes.py
│
├── core/
│   ├── agent_base.py
│   ├── messaging.py
│   └── orchestrator.py
│
├── data/
│   ├── storage/
│   ├── features/
│   └── ingestion/
│
├── config/
│   └── settings.py              ← CONFIGURATION (Layer 6)
│
├── scripts/
│   ├── migrations/              ← SCHEMA GOVERNANCE (Layer 7)
│   │   ├── 001_auth_schema.sql
│   │   ├── 002_copy_schema.sql
│   │   └── day5_runtime_config.sql
│   │
│   └── tests/                   ← TESTING (Layer 8)
│       ├── day5/
│       │   ├── test_auth_service.py
│       │   ├── test_copy_service.py
│       │   └── test_contracts.py
│       └── integration/
│
└── docs/
    ├── ARCHITECTURE_GOLD_STANDARD.md
    ├── BEST_STRUCTURED_BLUEPRINT.md
    └── [API docs, guides]
```

---

## TOP 5 ARCHITECTURAL MISTAKES TO AVOID

### ❌ MISTAKE 1: Endpoint Logic Creep

```python
# WRONG: Business logic in endpoint
@app.post("/copy/order")
async def place_order(order: OrderRequest):
    # Validation
    if order.qty > 100:
        raise ValueError("qty too high")
    
    # Calculation
    allocated_qty = order.qty * 0.5
    
    # DB write
    result = await db.insert("orders", {...})
    
    # Risk check
    risk = await db.query("SELECT * FROM positions WHERE ...")
    if risk.current_leverage > 2.0:
        raise ValueError("leverage too high")

# RIGHT: Delegate to service
@app.post("/copy/order")
async def place_order(
    order: OrderRequest,
    copy_service = Depends(get_copy_service)
):
    # Service handles everything
    result = await copy_service.place_order(order)
    return result
```

**Why it matters:**
- Logic duplication (API, CLI, cron job all write same logic)
- Security inconsistency (different auth contexts)
- Refactor pain (change logic in 5 places)

---

### ❌ MISTAKE 2: Direct DB from UI

```python
# WRONG: Dashboard queries DB directly
@app.get("/copy/logs")
async def copy_logs():
    # Dashboard could call this directly
    result = await db.query(
        "SELECT * FROM copy_execution_log WHERE created_at > NOW() - INTERVAL '1 day'"
    )
    return result

# RIGHT: Service provides interface
@app.get("/copy/logs")
async def copy_logs(copy_service = Depends(...)):
    # Service enforces consistency
    result = await copy_service.get_logs(days=1)
    return result

class CopyService:
    async def get_logs(self, days: int):
        # Service owns the query
        # Can add filtering, pagination, audit
        return await self.db.query(...)
```

**Why it matters:**
- Dashboard can't apply business rules
- Schema changes break UI
- No consistency guarantee
- No audit trail

---

### ❌ MISTAKE 3: Security as Wrapper, Not Foundation

```python
# WRONG: Security bolted on top
class CopyService:
    async def execute_copy(self, leader_id, follower_id):
        # No security awareness
        # Service assumes API already checked auth
        ...

@app.post("/copy")
async def copy(api_key = Depends(verify_token)):
    if api_key.role != "trader":
        raise HTTPException(403)
    # Only NOW call service
    return await copy_service.execute_copy(...)

# RIGHT: Security in foundation
class CopyService:
    async def execute_copy(self, leader_id, follower_id, actor_id: str):
        # Service knows who's doing this
        # Service can audit properly
        await self._audit_log("copy_executed", actor_id=actor_id)
        ...

@app.post("/copy")
async def copy(api_key = Depends(verify_token)):
    # Service inherently secure
    return await copy_service.execute_copy(..., actor_id=api_key.id)
```

**Why it matters:**
- Cron job loses audit context
- CLI tool can't use same service safely
- Refactor risks security hole
- Service can't enforce its own rules

---

### ❌ MISTAKE 4: No Event Lineage

```python
# WRONG: Action but no record
class CopyService:
    async def execute_copy(self, ...):
        # Something happens
        await self.db.insert("copy_execution_log", {...})
        # But what led to this copy?
        # What's the strategy genealogy?
        # No lineage

# RIGHT: Event lineage
class CopyService:
    async def execute_copy(self, ...):
        await self.db.insert("copy_events", {
            "action": "copy_executed",
            "timestamp": now(),
            "leader_order_id": ...,
            "follower_id": ...,
            "leader_strategy_id": ...,  # Lineage
            "leader_strategy_lineage": ...,  # Where did this come from?
            "reason": ...,
        })
```

**Why it matters:**
- Can't replay errors (what caused this copy?)
- Can't debug genealogy (which strategies work?)
- Can't audit compliance (what's the chain?)
- Can't analyze performance (which parents succeed?)

---

### ❌ MISTAKE 5: Subsystems Not Independently Operable

```python
# WRONG: Subsystem depends on API
class CopyTrader:
    async def run(self):
        # Can only be tested with full API setup
        # Can't run headless
        # Can't be used in cron job
        # Tightly coupled to FastAPI
        ...

# RIGHT: Subsystem independent
class CopyTrader:
    def __init__(self, db, risk_service, logger):
        # Can be tested standalone
        # Can be used as library
        # Can run headless
        # Can be used in cron, CLI, batch
        ...

    async def run(self):
        # Pure trading logic
        # No API knowledge
        # No FastAPI dependency
        ...

# Usage (flexible)
# Option 1: In API
@app.get("/copy")
async def copy(copy_trader = Depends(...)):
    return await copy_trader.execute()

# Option 2: Headless / cron
async def main():
    trader = CopyTrader(db, risk, logger)
    await trader.run()

# Option 3: CLI
async def cli():
    trader = CopyTrader(db, risk, logger)
    await trader.execute_single_order(order_id)
```

**Why it matters:**
- Testability (no need for HTTP server)
- Reusability (CLI, cron, batch jobs)
- Failover (can run independently)
- Deployment (multiple topologies)

---

## GOVERNANCE QUALITY GATE

**For every new subsystem, ask:**

```
"If this subsystem had to:
  □ Scale independently
  □ Survive restart
  □ Be audited after failure
  □ Run headless
  □ Be tested in isolation

...would this design still be correct?

If NO → Refactor before shipping.
If MAYBE → Reconsider architecture.
If YES → Ship it.
```

---

## IDEAL IMPLEMENTATION ORDER (Days 5-7)

### NOW (Day 5 Phase A):
- ✅ AuthService (DONE)
- → RateLimitService (2 hours)

### Day 5 Phase B (4-6 hours):
- CopyService (extract from copy_trader)
- RiskService (extract from risk checks)
- HealthService (extract from health endpoint)

### Day 5 Phase C (8 hours):
- Dashboard prototype
- Real-time UI binding
- Management interface

### Day 6 (12 hours):
- Write APIs (POST endpoints)
- StrategyService
- Portfolio tracking

### Day 7+ (ongoing):
- Advanced services
- Multi-broker support
- Notification system

**Why this order:**
```
Services first (foundation)
→ Dashboard (visibility)
→ Write controls (capability)
→ Advanced features (sophistication)

NOT:

Features first
→ Services later (too late, debt everywhere)
```

---

## FINAL "BEST-STRUCTURED" CHECKLIST

Before shipping ANY module (service, API, dashboard):

### Architecture:
- ✅ Clear domain responsibility (one thing)
- ✅ Service abstraction (not inline logic)
- ✅ Idempotent operations (safe restart)
- ✅ Independent testing (no external deps)
- ✅ Observable failures (logged, audited)
- ✅ State machine explicit (not booleans)
- ✅ Configuration external (not hardcoded)

### Governance:
- ✅ Event/audit trail (immutable record)
- ✅ Security in foundation (not wrapper)
- ✅ Scope enforcement (least privilege)
- ✅ Rate limiting hooks (ready for throttling)
- ✅ Error handling typed (not generic)

### Quality:
- ✅ Unit tests (logic in isolation)
- ✅ Integration tests (with DB)
- ✅ Contract tests (API ↔ DB sync)
- ✅ Smoke tests (critical path)
- ✅ Security tests (auth, scope, rate limit)

### Documentation:
- ✅ Docstrings (why, not what)
- ✅ Examples (how to use)
- ✅ Error codes (what can fail)
- ✅ Integration guide (how to add to API)

---

## SIGN-OFF: BEST-STRUCTURED BLUEPRINT

**This blueprint ensures:**

1. ✅ **Modular infrastructure** — Each subsystem replaceable
2. ✅ **Security by design** — Not bolted on
3. ✅ **Operational resilience** — Crash-safe, audit-ready
4. ✅ **Future scale** — Horizontally scalable
5. ✅ **Institutional quality** — Production-grade

**ATLAS will become progressively harder to break as it becomes more powerful.**

---

**Generated:** May 16, 2026  
**Status:** Enforcement Mandate ✅  
**Applies To:** All future work (Days 5-∞)  
**Quality Target:** Institutional Infrastructure

**Build like you're building for scale. You are.**
