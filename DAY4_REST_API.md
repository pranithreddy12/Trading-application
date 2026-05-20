# Day 4 REST API Documentation

**Version:** 1.0.0  
**Status:** ✅ Production-Ready (Read APIs)  
**Authentication:** Bearer Token (shared token for Day 4)  
**Base URL:** `http://localhost:8000` (default)

---

## Quick Start

### 1. Start the API Server

```bash
cd c:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS
uvicorn atlas.api.day4_api:app --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 2. Make Authenticated Requests

All requests require a Bearer token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-16T13:30:00.000000",
  "components": {
    "database": "connected",
    "copy_trader": "running",
    "api": "operational"
  },
  "latency_ms": 15,
  "version": "1.0.0"
}
```

---

## Endpoints

### 1. `GET /health` — System Health

**Purpose:** Check API and subsystem health  
**Auth:** Required  
**Response Time:** <50ms

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-16T13:30:00.000000",
  "components": {
    "database": "connected",
    "copy_trader": "running",
    "api": "operational"
  },
  "latency_ms": 12,
  "version": "1.0.0"
}
```

**Error (503 Service Unavailable):**
```json
{
  "detail": "Database error: connection refused"
}
```

---

### 2. `GET /copy/logs` — Copy Execution History

**Purpose:** Query copy trading audit trail  
**Auth:** Required  
**Response Time:** <100ms

**Query Parameters:**
- `limit` (int, 1-100, default=20) — Number of records to return
- `status` (string, optional) — Filter by `filled`, `skipped`, or `failed`
- `symbol` (string, optional) — Filter by symbol (e.g., `NVDA`)

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  "http://localhost:8000/copy/logs?limit=5&status=filled"
```

**Response (200 OK):**
```json
{
  "count": 2,
  "logs": [
    {
      "id": "3f7a8c2d-1b94-4e6f-a8f1-9c7e2d5b1a4f",
      "leader_order_id": "e0075e50-1b45-460b-82ca-3ec11561d0f5",
      "follower_order_id": "a1b2c3d4-e5f6-4g7h-8i9j-0k1l2m3n4o5p",
      "leader_id": "87bf6ffa-d639-4403-9c6b-fa24235c05b5",
      "follower_id": "7416c767-c7e7-401b-90c7-e4e5b242b3ca",
      "symbol": "NVDA",
      "side": "buy",
      "leader_qty": 10,
      "follower_qty": 5,
      "latency_ms": 97,
      "status": "filled",
      "failure_reason": null,
      "created_at": "2026-05-16T13:22:22.000000"
    }
  ],
  "latency_ms": 8
}
```

---

### 3. `GET /leaders` — Leader Accounts

**Purpose:** List all configured leader accounts  
**Auth:** Required  
**Response Time:** <50ms

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/leaders
```

**Response (200 OK):**
```json
{
  "count": 1,
  "leaders": [
    {
      "leader_id": "87bf6ffa-d639-4403-9c6b-fa24235c05b5",
      "account_ref": "SIM_LEADER_001",
      "broker": "local",
      "is_active": true,
      "created_at": "2026-05-16T13:00:00.000000",
      "metadata": {}
    }
  ],
  "latency_ms": 5
}
```

---

### 4. `GET /followers` — Follower Accounts

**Purpose:** List all configured follower accounts  
**Auth:** Required  
**Response Time:** <50ms

**Query Parameters:**
- `leader_id` (string, optional) — Filter by leader ID

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/followers
```

**Response (200 OK):**
```json
{
  "count": 1,
  "followers": [
    {
      "follower_id": "7416c767-c7e7-401b-90c7-e4e5b242b3ca",
      "leader_id": "87bf6ffa-d639-4403-9c6b-fa24235c05b5",
      "account_ref": "SIM_FOLLOWER_001",
      "broker": "local",
      "allocation_ratio": 0.5,
      "max_position_pct": 0.1,
      "is_active": true,
      "created_at": "2026-05-16T13:01:00.000000",
      "metadata": {}
    }
  ],
  "latency_ms": 4
}
```

---

### 5. `GET /portfolio` — Portfolio Summary (Placeholder)

**Purpose:** Portfolio overview (full implementation Day 5)  
**Auth:** Required  
**Response Time:** <10ms

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/portfolio
```

**Response (200 OK):**
```json
{
  "status": "placeholder",
  "message": "Full portfolio tracking available in Day 5",
  "leaders": {"total": 1, "active": 1},
  "followers": {"total": 1, "active": 1},
  "latency_ms": 2
}
```

---

### 6. `GET /risk` — Risk Metrics (Placeholder)

**Purpose:** Portfolio risk analysis (full implementation Day 5)  
**Auth:** Required  
**Response Time:** <10ms

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/risk
```

**Response (200 OK):**
```json
{
  "status": "placeholder",
  "message": "Full risk metrics available in Day 5",
  "portfolio_var": null,
  "max_drawdown": null,
  "leverage_ratio": null,
  "latency_ms": 1
}
```

---

### 7. `GET /strategies` — Validated Strategies

**Purpose:** Query validated strategies with Day-4 metrics  
**Auth:** Required  
**Response Time:** <100ms

**Query Parameters:**
- `status` (string, optional) — Filter by `elite`, `validated`, or `research_candidate`
- `limit` (int, 1-50, default=10) — Number of strategies to return

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  "http://localhost:8000/strategies?status=elite&limit=5"
```

**Response (200 OK):**
```json
{
  "count": 1,
  "strategies": [
    {
      "id": "a1b2c3d4-e5f6-4g7h-8i9j-0k1l2m3n4o5p",
      "name": "MA_Crossover_Daily",
      "author_agent": "IdeatorV2_rich_01",
      "status": "elite",
      "validation_metrics": {
        "train_sharpe": 1.8,
        "test_sharpe": 1.6,
        "stability_score": 0.92,
        "overfit_flag": false
      },
      "created_at": "2026-05-16T12:00:00.000000"
    }
  ],
  "latency_ms": 45
}
```

---

### 8. `GET /status` — Comprehensive Status

**Purpose:** Overall system status and metrics  
**Auth:** Required  
**Response Time:** <100ms

**Request:**
```bash
curl -H "Authorization: Bearer atlas_day4_shared_token" \
  http://localhost:8000/status
```

**Response (200 OK):**
```json
{
  "timestamp": "2026-05-16T13:30:00.000000",
  "copy_trader": {
    "status": "operational",
    "filled_orders": 2,
    "skipped_orders": 0,
    "avg_latency_ms": 97.0
  },
  "accounts": {
    "leaders": 1,
    "followers": 1
  },
  "latency_ms": 12
}
```

---

## Authentication

### Bearer Token Format

All requests require an `Authorization` header with Bearer token:

```
Authorization: Bearer atlas_day4_shared_token
```

### Invalid Token

**Request:**
```bash
curl -H "Authorization: Bearer invalid_token" \
  http://localhost:8000/health
```

**Response (403 Forbidden):**
```json
{
  "detail": "Invalid API token"
}
```

### Missing Token

**Request:**
```bash
curl http://localhost:8000/health
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Missing Authorization header"
}
```

---

## Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid query parameters |
| 401 | Unauthorized | Missing Authorization header |
| 403 | Forbidden | Invalid or expired token |
| 500 | Internal Server Error | Database connection failure |
| 503 | Service Unavailable | Database offline |

---

## Performance Targets

| Endpoint | Target | Typical |
|----------|--------|---------|
| `/health` | <50ms | 12ms |
| `/copy/logs` | <100ms | 8ms |
| `/leaders` | <50ms | 5ms |
| `/followers` | <50ms | 4ms |
| `/status` | <100ms | 12ms |
| `/strategies` | <100ms | 45ms |

---

## Testing

### Run Full API Test Suite

```bash
# Make sure copy trader is running
python -m atlas.agents.l5_execution.copy_trader &

# In another terminal, start API
uvicorn atlas.api.day4_api:app --host 0.0.0.0 --port 8000 &

# In third terminal, run tests
python scripts/tests/day4/test_day4_api.py
```

### Expected Output

```
======================================================================
DAY 4 REST API ENDPOINT TESTS
======================================================================
API Base URL: http://localhost:8000
Timestamp: 2026-05-16T13:30:00.000000

[1/7] Testing /health endpoint...
✓ Status: healthy
  - Components: {'database': 'connected', 'copy_trader': 'running', 'api': 'operational'}
  - Latency: 12ms

[2/7] Testing /copy/logs endpoint...
✓ Found 2 execution(s)
  - Latency: 8ms
  - Latest: NVDA buy (leader=10, follower=5) status=filled

[3/7] Testing /leaders endpoint...
✓ Found 1 leader(s)
  - SIM_LEADER_001 (broker: local, active: True)

[4/7] Testing /followers endpoint...
✓ Found 1 follower(s)
  - SIM_FOLLOWER_001 (ratio: 0.5, max_pct: 0.1, active: True)

[5/7] Testing /status endpoint...
✓ Copy Trader Status: operational
  - Filled orders: 2
  - Skipped orders: 0
  - Avg latency: 97.0ms
  - Leaders: 1, Followers: 1

[6/7] Testing /strategies endpoint...
✓ Found 1 strateg(ies)
  - MA_Crossover_Daily (elite) by IdeatorV2_rich_01

[7/7] Testing authentication (invalid token should fail)...
✓ Auth rejection works: Invalid API token

======================================================================
API TEST SUMMARY
======================================================================
✓ All endpoints accessible with valid Bearer token
✓ Authentication enforced (invalid tokens rejected)
✓ API reflects actual system state (not placeholders)
✓ Latency measurements included in all responses

Day 4 API Ready for Integration!
```

---

## Day 5 Roadmap

**Planned Enhancements:**
1. Write APIs (POST/PUT/DELETE)
2. RBAC (role-based access control)
3. Full portfolio tracking
4. Advanced risk metrics
5. Strategy lifecycle management (publish, retire, etc.)
6. Webhook notifications
7. Rate limiting
8. API key management

---

## Support

**Configuration:**
- API Token: Set via environment variable `API_TOKEN` or use default
- Port: Configure via `--port` argument to uvicorn
- Host: Configure via `--host` argument to uvicorn

**Debugging:**
- Enable verbose logging: `--log-level debug`
- Check API docs: http://localhost:8000/docs (auto-generated by FastAPI)

---

**Status:** ✅ Production-Ready for Read Operations  
**Last Updated:** May 16, 2026
