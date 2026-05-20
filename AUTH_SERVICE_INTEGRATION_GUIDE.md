# AuthService Integration Guide

**Date:** May 16, 2026  
**Status:** Day 5 Phase A Priority 1 (First Gold Standard Subsystem)  
**Purpose:** Institutional-grade authentication for ATLAS API

---

## OVERVIEW

AuthService is the **first architecturally pure subsystem** implementing the ATLAS Gold Standard:

✅ **Service abstraction** — Business logic separated from API  
✅ **Security-first** — RBAC + scope enforcement + audit logging  
✅ **Data integrity** — Hashed keys, atomic operations  
✅ **Idempotency** — Safe revocation, replay-safe  
✅ **Observability** — Every action logged  
✅ **Testability** — Full test coverage (unit + integration + smoke)  

---

## ARCHITECTURE

```
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
    ┌────▼─────────────────┐
    │ AuthMiddleware       │
    │ (dependency inject)  │
    └────┬─────────────────┘
         │
    ┌────▼──────────────────┐
    │ AuthService          │
    │ (business logic)      │
    │ - generate_key()     │
    │ - validate_key()     │
    │ - check_scope()      │
    │ - revoke_key()       │
    │ - log_request()      │
    └────┬─────────────────┘
         │
    ┌────▼────────────────┐
    │  PostgreSQL/Timescale
    │  - api_keys table
    │  - api_request_audit
    │  - audit_logs table
    └─────────────────────┘
```

---

## QUICK START

### 1. Apply Migration

```bash
# Apply auth schema
psql $DATABASE_URL < scripts/migrations/day5_auth_schema.sql

# Verify tables created
psql $DATABASE_URL -c "\dt api_keys;"
psql $DATABASE_URL -c "\dt api_request_audit;"
psql $DATABASE_URL -c "\dt audit_logs;"
```

### 2. Initialize AuthService in FastAPI

```python
# In main API file (e.g., atlas/api/day4_api.py or day5_api.py)

from fastapi import FastAPI
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.api.services.auth_service import AuthService
from atlas.api.middleware.auth_middleware import AuthMiddleware, set_auth_middleware

app = FastAPI(title="ATLAS Day 5 API")

# Initialize services
db = TimescaleClient(settings.database_url)
auth_service = AuthService(db)
auth_middleware = AuthMiddleware(auth_service)

# Set global middleware (needed for dependency injection)
set_auth_middleware(auth_middleware)

@app.on_event("startup")
async def startup():
    await db.connect()
    logger.info("AuthService initialized")
```

### 3. Protect Endpoints

```python
from fastapi import Depends
from atlas.api.middleware.auth_middleware import (
    verify_token,
    verify_admin_token,
    verify_trader_token,
    verify_read_token
)

# Read endpoint (any authenticated user)
@app.get("/copy/logs")
async def copy_logs(api_key = Depends(verify_read_token)):
    """Get copy execution history"""
    logger.info(f"User {api_key.user_id} accessing copy logs")
    return {"logs": [...]}

# Write endpoint (trader or admin)
@app.post("/copy/order")
async def place_order(order: OrderRequest, api_key = Depends(verify_trader_token)):
    """Place copy order"""
    logger.info(f"Trader {api_key.user_id} placing order")
    return {"order_id": "..."}

# Admin endpoint
@app.post("/admin/keys")
async def revoke_key(key_id: str, api_key = Depends(verify_admin_token)):
    """Revoke API key (admin only)"""
    await auth_service.revoke_key(key_id, revoked_by=api_key.user_id, reason="Admin revocation")
    return {"status": "revoked"}
```

---

## API KEY LIFECYCLE

### Generate New Key

```python
# For a trader
raw_key, key_id = await auth_service.generate_api_key(
    user_id="trader@company.com",
    role=APIRole.TRADER,
    created_by="admin@company.com",
    description="Trader API key",
    rate_limit_per_min=100
)

# Give user the raw key ONCE
print(f"Share this key: {raw_key}")
print(f"Store this ID: {key_id}")

# Never show raw_key again (it's only returned once)
```

### Validate Key

```python
# AuthMiddleware does this automatically via dependency injection
# But can also call directly:

api_key = await auth_service.validate_key(raw_key)

if api_key and api_key.is_valid():
    print(f"Valid key: {api_key.role}")
else:
    print("Invalid or expired key")
```

### Check Scope

```python
# AuthMiddleware does this for explicit scopes
# Can also verify manually:

allowed = api_key.can_access_endpoint("/copy/logs", "GET")

if not allowed:
    raise HTTPException(status_code=403, detail="Access denied")
```

### Revoke Key

```python
# Soft delete (preserves history for audit trail)
await auth_service.revoke_key(
    key_id=key_id,
    revoked_by="admin@company.com",
    reason="User requested, switching to new key"
)

# Key now invalid for future requests
```

---

## ROLE-BASED ACCESS CONTROL

### Roles

```python
class APIRole(str, Enum):
    ADMIN = "admin"          # Full access, admin operations
    TRADER = "trader"        # Execute orders, read operations
    READ_ONLY = "read_only"  # Only GET endpoints
    FOLLOWER = "follower"    # View leader trades only
    MONITOR = "monitor"      # Health/status only
```

### Role Capabilities

| Role | GET /copy/logs | GET /health | POST /copy/order | DELETE /followers | POST /admin |
|------|---|---|---|---|---|
| **admin** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **trader** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **read_only** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **follower** | ✅ (leader trades) | ✅ | ❌ | ❌ | ❌ |
| **monitor** | ❌ | ✅ | ❌ | ❌ | ❌ |

### Assignment

```python
# Admin role (system access)
raw_key, _ = await auth_service.generate_api_key(
    user_id="admin@atlas.io",
    role=APIRole.ADMIN,
    created_by="system"
)

# Trader role (operations)
raw_key, _ = await auth_service.generate_api_key(
    user_id="trader@fund.com",
    role=APIRole.TRADER,
    created_by="admin@atlas.io",
    rate_limit_per_min=200
)

# Monitor role (read-only status)
raw_key, _ = await auth_service.generate_api_key(
    user_id="ops@atlas.io",
    role=APIRole.MONITOR,
    created_by="admin@atlas.io"
)
```

---

## USAGE EXAMPLE

### Client Request

```bash
# Generate key first
curl -X POST http://localhost:8000/admin/keys/generate \
  -H "Authorization: Bearer atlas_admin_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "trader@fund.com",
    "role": "trader",
    "description": "Fund trader key"
  }'

# Response
{
  "raw_key": "atlas_abc123def456...",  # SHARE ONCE
  "key_id": "uuid-...",                 # Store this
  "role": "trader",
  "created_at": "2026-05-16T14:23:41Z"
}

# Now use key to access API
curl -H "Authorization: Bearer atlas_abc123def456..." \
  http://localhost:8000/copy/logs

# Response
{
  "status": "success",
  "latency_ms": 42,
  "logs": [...]
}
```

---

## AUDIT TRAIL

### Request Logging

Every request is logged to `api_request_audit` table:

```sql
SELECT 
    endpoint, 
    method, 
    status_code, 
    latency_ms, 
    created_at
FROM api_request_audit
WHERE api_key_id = 'uuid-...'
ORDER BY created_at DESC
LIMIT 10;
```

### High-Stakes Operations

Key creation, revocation, role changes logged to `audit_logs`:

```sql
SELECT 
    action, 
    actor_id, 
    status, 
    reason,
    old_value,
    new_value,
    timestamp
FROM audit_logs
WHERE action IN ('create_api_key', 'revoke_api_key')
ORDER BY timestamp DESC;
```

### Compliance Ready

```sql
-- Who accessed what and when?
SELECT 
    a.user_id, 
    a.endpoint, 
    COUNT(*) as request_count,
    MAX(a.created_at) as last_accessed
FROM api_request_audit a
WHERE a.created_at > NOW() - INTERVAL '30 days'
GROUP BY a.user_id, a.endpoint
ORDER BY request_count DESC;

-- Who has what permissions?
SELECT 
    user_id, 
    role, 
    is_active, 
    rate_limit_per_min, 
    created_at, 
    last_used_at
FROM api_keys
WHERE revoked_at IS NULL
ORDER BY created_at DESC;
```

---

## SECURITY BEST PRACTICES

### For API Developers

✅ **DO:**
```python
# Always use dependency injection
async def my_endpoint(api_key = Depends(verify_token)):
    # AuthService already validated
    logger.info(f"User {api_key.user_id} accessed endpoint")
```

✅ **DO:**
```python
# Check role for sensitive operations
async def admin_endpoint(api_key = Depends(verify_admin_token)):
    # Already verified role is admin
```

✅ **DO:**
```python
# Log user actions
await auth_service.log_request(...)
```

❌ **DON'T:**
```python
# Never call validate directly if middleware exists
api_key = await auth_service.validate_key(token)  # Unnecessary

# Use dependency instead:
async def endpoint(api_key = Depends(verify_token)):
    ...
```

❌ **DON'T:**
```python
# Never check hardcoded tokens
if token == "secret_token":  # WRONG
    ...

# Use AuthService:
api_key = await auth_service.validate_key(token)  # RIGHT
```

### For Users

✅ **DO:**
```bash
# Store key securely
export ATLAS_API_KEY="atlas_abc123..."

# Use in requests
curl -H "Authorization: Bearer $ATLAS_API_KEY" http://localhost:8000/health
```

✅ **DO:**
```bash
# Rotate keys periodically
# Request new key, revoke old key
```

❌ **DON'T:**
```bash
# Never commit keys to version control
git add .env  # WRONG - will leak keys

# Use .env files
echo "ATLAS_API_KEY=..." > .env
echo ".env" >> .gitignore
```

---

## TESTING

### Run Auth Service Tests

```bash
# All tests
pytest scripts/tests/day5/test_auth_service.py -v

# Specific test
pytest scripts/tests/day5/test_auth_service.py::test_validate_key_success -v

# With coverage
pytest scripts/tests/day5/test_auth_service.py --cov=atlas.api.services.auth_service
```

### Test Categories

- **Unit Tests:** Key generation, hashing, revocation
- **Integration Tests:** With real (test) DB
- **Smoke Tests:** Full lifecycle flows
- **Security Tests:** Invalid keys, expired keys, revoked keys, scope denial

---

## MONITORING & ALERTS

### Queries for Ops

```sql
-- High failed auth attempts in last hour
SELECT endpoint, COUNT(*) as failures
FROM api_request_audit
WHERE status_code = 401 AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY endpoint
ORDER BY failures DESC;

-- Keys not used in last 30 days
SELECT user_id, description, created_at, last_used_at
FROM api_keys
WHERE revoked_at IS NULL
  AND (last_used_at IS NULL OR last_used_at < NOW() - INTERVAL '30 days')
ORDER BY last_used_at;

-- Revoked keys (audit trail)
SELECT user_id, revoked_at, revoke_reason, revoked_by
FROM api_keys
WHERE revoked_at IS NOT NULL
ORDER BY revoked_at DESC
LIMIT 20;
```

---

## NEXT STEPS (Day 5 Phases)

### Phase A-1: ✅ DONE
- ✅ AuthService core logic
- ✅ API key schema
- ✅ Middleware
- ✅ Tests

### Phase A-2: Rate Limiting
- Redis token bucket
- Per-key rate limit enforcement
- X-RateLimit-* headers

### Phase A-3: Dashboard Integration
- Key management UI
- Usage analytics
- Revocation interface

### Phase B: Service Extraction
- CopyService
- RiskService
- HealthService

---

## TROUBLESHOOTING

### "Invalid Authorization header"
```
Problem: Bearer token malformed
Solution: Use "Authorization: Bearer <token>" format
```

### "Access denied"
```
Problem: Role doesn't have permission
Solution: Check role (admin, trader, read_only, follower, monitor)
          Use lower-privilege role test key
```

### "API key not found"
```
Problem: Key was revoked or expired
Solution: Generate new key
          Check expiry date
          Verify key prefix (should be "atlas_")
```

### "Rate limit exceeded"
```
Problem: Too many requests
Solution: Wait 1 minute and retry
          Check rate_limit_per_min setting
          Request higher limit from admin
```

---

## SIGN-OFF: FIRST GOLD STANDARD SUBSYSTEM

**Status:** ✅ Complete

This AuthService demonstrates that the ATLAS Gold Standard is not just documentation—it's a practical framework for building institutional-grade systems:

1. ✅ **Principle-driven:** Followed all 12 architectural principles
2. ✅ **Security-first:** RBAC, audit logging, hashed storage
3. ✅ **Service abstraction:** Business logic separated from API
4. ✅ **Fully tested:** Unit + integration + smoke tests
5. ✅ **Observable:** Every action logged, queryable audit trail
6. ✅ **Idempotent:** Safe restart, no duplicate mutations
7. ✅ **Maintainable:** Clear code, good documentation

**Next:** Use AuthService as the template for CopyService, RiskService, HealthService (Phase B).

---

**Generated:** May 16, 2026  
**Version:** Day 5 Phase A  
**Status:** Production Ready ✅
