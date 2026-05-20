# DAY 5 — HARDENING + DECISION ROADMAP

**Status:** Day 4 Complete & Validated  
**Current Score:** 9.1/10  
**Phase:** Operational Discipline & Platform Maturity  
**Date:** May 16, 2026

---

## STRATEGIC INFLECTION POINT

**Day 4 Achievement:**
```
Research Platform        →    Operational Platform
(Generate + Validate)    →    (Execute + API + Visibility)
```

**New Reality:**
- ATLAS is no longer a project
- ATLAS is the foundation of a product
- Execution trust > execution complexity

---

## PRIORITY HARDENING MATRIX

### PRIORITY 1 — API SECURITY REVIEW ⚠️ CRITICAL

**Current State:** Shared token (`atlas_day4_shared_token`)

**What to Build:**
```python
# New table: api_keys
- api_key_id (UUID)
- api_key (hashed)
- user_id / team_id
- roles (array: admin, read_only, trader, follower)
- is_active (boolean)
- created_at, expires_at
- last_used_at
- rate_limit_tier (free, pro, enterprise)

# New dependency in endpoints
async def verify_api_key(token: str) -> APIKeyRecord
```

**Roles to Define:**
```
admin         → All endpoints + admin actions
trader        → Write orders, portfolio management
read_only     → Only GET endpoints
follower      → View leader trades only
monitor       → Health/status only
```

**Impact:** Unlocks multi-user demo capability

**Effort:** 3-4 hours  
**Risk:** Medium (auth is critical path)  
**Priority Justification:** Cannot proceed to write APIs without this

---

### PRIORITY 2 — API RATE LIMITING 🔒 HIGH

**Current State:** No throttling

**What to Build:**
```python
# In day4_api.py or new day5_api.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/health")
@limiter.limit("100/minute")
async def health(): ...

@app.get("/copy/logs")
@limiter.limit("30/minute")
async def copy_logs(): ...
```

**Rate Limits Suggested:**
```
/health          → 100/min    (monitoring)
/copy/logs       → 30/min     (read-heavy)
/leaders         → 30/min
/followers       → 30/min
/portfolio       → 20/min     (expensive query)
/risk            → 20/min
/strategies      → 20/min
/status          → 50/min
```

**Impact:** Prevents accidental DoS, demo crashes

**Effort:** 1-2 hours  
**Risk:** Low  
**Priority Justification:** Prevents embarrassing demo failures

---

### PRIORITY 3 — `/copy/status` ENDPOINT 📊 MEDIUM

**Current State:** Only `/copy/logs` exists (historical)

**What to Build:**
```python
@app.get("/copy/status")
async def copy_status(token: str = Depends(verify_token)):
    """Current subsystem state (not historical)"""
    return {
        "copy_trader": {
            "status": "running",           # running | idle | error
            "uptime_seconds": 3847,
            "last_heartbeat_ms_ago": 234,
            "followers_active": 1,
            "leaders_active": 1,
            "orders_per_second": 0.12
        },
        "latest_copy": {
            "leader_order_id": "uuid-123",
            "follower_id": "SIM_FOLLOWER_001",
            "copied_at": "2026-05-16T13:45:23Z",
            "latency_ms": 97,
            "status": "filled"
        },
        "redis": {
            "status": "connected",
            "ping_ms": 1
        },
        "database": {
            "status": "connected",
            "query_avg_ms": 12,
            "open_connections": 3
        },
        "api": {
            "uptime_seconds": 892,
            "requests_per_second": 2.4,
            "errors_last_minute": 0,
            "current_user_count": 1
        },
        "measured_at": "2026-05-16T13:47:41Z"
    }
```

**Why This Matters:**
- Dashboards need live subsystem state
- Investors see real operational health
- Ops team catches problems early
- Not just "up" but "how well"

**Effort:** 1-2 hours  
**Risk:** Low  
**Priority Justification:** High demo impact, low effort

---

### PRIORITY 4 — API/DB CONTRACT TESTS 🧪 MEDIUM

**Current State:** Smoke tests exist; no contract verification

**What to Build:**
```python
# scripts/tests/day5/test_api_db_contracts.py

async def test_leaders_count_matches():
    """GET /leaders count == SELECT COUNT(*) from copy_leader_accounts"""
    # Get from API
    api_leaders = await http_get("/leaders")
    api_count = len(api_leaders["data"])
    
    # Get from DB
    db_count = await db.scalar(
        "SELECT COUNT(*) FROM copy_leader_accounts WHERE is_active=true"
    )
    
    assert api_count == db_count, f"Contract broken: API={api_count}, DB={db_count}"

async def test_follower_subscriptions_match():
    """GET /followers matches copy_follower_accounts"""
    
async def test_copy_log_filtering_matches():
    """GET /copy/logs?status=filled matches DB query"""
    
async def test_strategy_validation_status_matches():
    """GET /strategies?status=elite matches DB query"""
```

**Why This Matters:**
- Catches silent API drift
- DB schema changes break API silently without this
- CI/CD confidence

**Effort:** 2 hours  
**Risk:** Low  
**Priority Justification:** Operational discipline requirement

---

### PRIORITY 5 — DEEPER `/health` CHECKS 💚 MEDIUM

**Current State:** Basic system check

**Enhancement:**
```python
@app.get("/health")
async def health():
    """Deep operational health, not just process alive"""
    
    checks = {
        "database": await check_db(),          # Connect + query
        "redis": await check_redis(),          # Ping + set/get
        "copy_trader": await check_copy_trader(),  # Alive? Last order?
        "validator": await check_validator(),    # Alive? Last validation?
        "api": await check_api(),              # Uptime, request rate
    }
    
    # Overall status: "healthy", "degraded", "critical"
    status = "healthy"
    if any(c["status"] == "error" for c in checks.values()):
        status = "critical"
    elif any(c["status"] == "warning" for c in checks.values()):
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow(),
        "checks": checks,
        "latency_ms": measured_latency
    }
```

**Effort:** 1-2 hours  
**Risk:** Low  
**Priority Justification:** Monitoring & alerting foundation

---

## DAY 5 DECISION FRAMEWORK

### **THE CHOICE: PATH A vs PATH B**

#### **PATH A: DASHBOARD FIRST**

**Build:** Real-time web UI showing:
```
- Leaders & followers (live table)
- Copy execution log (streaming)
- Portfolio state
- Risk metrics
- System health
```

**Pros:**
- Immediate demo impact
- Visual credibility multiplier
- Faster investor conversations
- UI drives backend polish

**Cons:**
- Requires frontend (TypeScript/React/Vue)
- New tech stack to maintain
- Can't be automated yet

**Best For:** Demo strength, visual impact

**Effort:** 8-12 hours (React + real-time)

---

#### **PATH B: WRITE APIs + RBAC**

**Build:** Programmatic control plane:
```
POST /copy/order        → Place mirror order
POST /followers         → Create follower
PUT /followers/{id}     → Adjust allocation
DELETE /followers/{id}  → Remove follower
POST /strategies        → Register strategy
```

**Pros:**
- Automation ready
- Enables external dashboards
- Integrates with existing tools
- Multi-user capable
- Webhook-ready

**Cons:**
- No visual wow-factor
- Requires more API discipline
- Documentation-heavy

**Best For:** Platform maturity, automation

**Effort:** 6-8 hours

---

### **RECOMMENDATION: DASHBOARD FIRST**

**Reasoning:**

1. **Your backend is already ahead**
   - Copy trader works
   - API reads are solid
   - DB schema is stable
   - Real data exists

2. **Dashboard compounds value quickly**
   - Real-time visuals drive demos
   - Backend polish becomes visible
   - Investors understand "production"
   - One thing that matters: does it LOOK operational?

3. **Then immediately write APIs + RBAC**
   - Dashboard uses same API layer
   - Write APIs follow same pattern
   - RBAC applies to both
   - You're not delaying maturity, just sequencing for impact

4. **Suggested Day 5 Order:**
   ```
   Phase 1 (2-3 hrs):  Harden priorities 1-5 above
   Phase 2 (8 hrs):    Build dashboard prototype
   Phase 3 (4 hrs):    Write API skeleton
   Phase 4 (3 hrs):    RBAC core
   ```

---

## ENGINEERING PHILOSOPHY FOR DAY 5+

### New Rule:

**Every new module must answer:**

```
Does this improve:
  1. Execution trust?
  2. Visibility?
  3. Control?

If not → deprioritize
```

### Examples:

✅ **KEEP:** `/copy/status` (visibility)  
✅ **KEEP:** RBAC (control)  
✅ **KEEP:** Rate limiting (trust)  
❌ **SKIP:** Advanced ML strategy picker (not trusted yet)  
❌ **SKIP:** Complex portfolio optimization (not visible yet)  
✅ **KEEP:** Contract tests (trust)  

---

## DAY 5 DELIVERABLES (IF PATH A)

### Deliverable 1: Hardening
- ✅ API key + roles table
- ✅ Rate limiting middleware
- ✅ `/copy/status` endpoint
- ✅ API/DB contract tests
- ✅ Deep `/health` checks

### Deliverable 2: Dashboard
- ✅ Live leader/follower table
- ✅ Execution log (scrollable, filterable)
- ✅ Real-time status cards
- ✅ Health indicator
- ✅ React setup (TypeScript)

### Deliverable 3: Integration
- ✅ Dashboard ↔ API live binding
- ✅ WebSocket for streaming (optional)
- ✅ Error handling & empty states

**Expected Result:** Full-featured operational dashboard with live data

---

## DAY 5 DELIVERABLES (IF PATH B)

### Deliverable 1: Hardening
(Same as above)

### Deliverable 2: Write APIs
- ✅ `POST /copy/order`
- ✅ `POST /followers`
- ✅ `PUT /followers/{id}`
- ✅ `DELETE /followers/{id}`
- ✅ `POST /strategies`

### Deliverable 3: RBAC
- ✅ API key scoping
- ✅ Role enforcement
- ✅ Audit logging

**Expected Result:** Full programmatic control + multi-user support

---

## DEMO SCRIPT (POST-DAY-5)

```
1. [System Health] Show /health dashboard
   "All subsystems running"

2. [Strategy] Show generated strategy
   "Autonomously generated and validated"

3. [Copy Trade Demo]
   - Lead order placed
   - Follower mirrored (real-time on dashboard)
   - Latency: 97ms
   - Audit trail visible in /copy/logs

4. [API Access]
   curl /copy/logs → Shows copy execution
   curl /status → Shows live state

5. [RBAC Demo] (Day 5)
   "Multiple users, role-scoped access"

6. [Close]
   "Institutional-grade autonomous trading platform"
```

---

## SIGN-OFF: DAY 4 → DAY 5 TRANSITION

### Day 4 Freeze Status: ✅ LOCKED

- Copy trader: Operational
- REST API: Read-first, production code
- Schema: Stable (leader_orders verified)
- Tests: Organized, repeatable
- Documentation: Complete

### Day 5 Mandate

**Focus:** Operational hardening + platform visibility  
**Philosophy:** Trust > complexity  
**Path:** Dashboard first, then write APIs  
**Rule:** Each feature must improve trust, visibility, or control

### Engineering Maturity Jump

```
Before:  "Does it work?"
Now:     "Can we operate it?"
Next:    "Can we scale it?"
```

---

**ATLAS is transitioning from prototype to product.**

**Day 5 is about making that transition visible.**

---

**Generated:** May 16, 2026  
**Status:** Ready for Day 5 Sprint Planning
