# DAY 5 — Live Validation Harness

**Date:** 2026-05-16  
**Status:** ✅ 10/10 PASS — Hardened & Certified  
**Asset Class:** Tier-1 Governance Truth Engine  
**Owner:** Pranith

---

## 1. Purpose

The Day 5 Live Validation Harness (`scripts/day5/live_validation.py`) is ATLAS's **Tier-1 governance truth engine**. It is not a test suite — it is a deployment validator, governance certifier, regression gate, and platform truth engine that validates the operational platform under adversarial runtime conditions.

The harness produces **deterministic, structured evidence** of system health and proves the architecture is operational-platform ready.

---

## 2. Validation Stages

| # | Stage | What It Validates | Defect Type |
|---|-------|-------------------|-------------|
| 01 | Schema Validation | 7 required Day 4 tables exist; auto-bootstraps missing | `schema_failure` |
| 02 | Key Generation | Generates 5 API keys (admin, trader, read_only, follower, monitor) | `auth_failure` |
| 03 | Route Authentication | 10 GET endpoints with admin (200) and read_only (200/403) | `auth_failure` |
| 04 | Rate Limiting | Key with 2/min limit → 429 on attempt 3 | `rate_limit_failure` |
| 05 | Health Verification | `/health` returns status, timestamp, latency_ms, components | `health_failure` |
| 06 | Copy Status | `/copy/status` returns timestamp, running_state, active counts | `serialization_failure` |
| 07 | Security Matrix | 4 roles × 5 endpoints: admin=PASS, revoked/invalid=UNAUTHORIZED | `permission_failure` |
| 08 | Audit Trail | api_request_audit > 0, audit_logs > 0, api_keys > 0 | `audit_failure` |
| 09 | Restart Certification | Auth cache cleared, keys re-validated, no state corruption | `restart_failure` |
| 10 | Latency Metrics | All stage latencies collected; any > 60s flagged | `latency_failure` |

---

## 3. Results

| Metric | Value |
|--------|-------|
| Total Stages | 10 |
| Passed | 10 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Overall | **PASS** |
| Max Stage Latency | 53,052ms (Stage 07 — Security Matrix) |
| Total Run Time | ~2 minutes |

### Latency Report

| Stage | Latency (ms) |
|-------|-------------|
| 01 Schema Validation | 36 |
| 02 Key Generation | 4,493 |
| 03 Route Auth | 42,776 |
| 04 Rate Limiting | 10,873 |
| 05 Health Verification | 1,705 |
| 06 Copy Status | 1,701 |
| 07 Security Matrix | 53,052 |
| 08 Audit Trail | 42 |
| 09 Restart Certification | 11,189 |

**Note:** Dominant latency is from bcrypt key validation (O(n) scan of all non-revoked keys). Pre-cleanup of stale keys is required.

---

## 4. Security Matrix

| Role | GET /health | GET /copy/logs | GET /leaders | GET /followers | GET /copy/status |
|------|-----------|--------------|------------|--------------|----------------|
| **admin** | PASS | PASS | PASS | PASS | PASS |
| **read_only** | PASS | PASS | PASS | PASS | PASS |
| **revoked** | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED |
| **invalid** | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED | UNAUTHORIZED |

**Findings:**
- Admin has full read access to all endpoints → PASS
- Read-only has equivalent GET access (intentional for monitoring) → PASS
- Revoked keys are properly rejected → PASS
- Invalid keys are properly rejected → PASS
- Rate limit is scoped per-key → confirmed

---

## 5. Critical Discoveries

### 5.1 bcrypt Key Validation Scalability (O(n) Problem)
`AuthService.validate_key()` scans ALL non-revoked `api_keys` rows and calls `bcrypt.checkpw()` on each. With ~500ms per check and 30+ stale keys, each API request takes ~15 seconds.  

**Mitigation:** Pre-cleanup step (`UPDATE api_keys SET revoked_at=NOW()`) is required before each validation run.

### 5.2 Rate Limit Trigger Semantics
With `rate_limit_per_min=2`, the 429 response is triggered on **attempt 3** (not attempt 2). This is correct fixed-window behavior (first 2 requests pass, 3rd is blocked).

### 5.3 Two API Servers Exist
- **Port 8000** — `day4_api.py` (authenticated, copy trading + health). Validated by this harness.
- **Port 8080** — `main.py` (dashboard API, no auth, WebSocket support). NOT validated by this harness.

### 5.4 Schema Auto-Bootstrap Works
The harness can bootstrap all 7 Day 4 tables if they are missing. Only `positions` was missing in initial runs — all others already existed from earlier work.

---

## 6. Architecture & Usage

### Files

| File | Purpose |
|------|---------|
| `scripts/day5/live_validation.py` | Main harness (1719 lines, 10 stages) |
| `scripts/day5/bootstrap_day4_schema.sql` | Reference SQL for manual bootstrap |
| `scripts/day5/validation_output.json` | Deterministic JSON output from last run |
| `scripts/day5/validation.log` | Full debug log from last run |

### Prerequisites

1. PostgreSQL + Redis running (via `docker-compose` or local)
2. Day 4 API server running on port 8000:
   ```bash
   cd /path/to/atlas
   python -m uvicorn atlas.api.day4_api:app --host 0.0.0.0 --port 8000
   ```
3. Python 3.11+ with dependencies installed

### Running

```bash
cd /path/to/atlas
python -m scripts.day5.live_validation
```

### Output

- Always writes `scripts/day5/validation_output.json` — even on crash/exception
- Failure exit code (1) if overall status ≠ PASS
- Debug log written to `scripts/day5/validation.log`

---

## 7. Rules Enforced

1. Always writes output JSON (even on partial failure / exceptions)
2. Stage isolation — each stage commits/rolls back independently
3. Live defect classification — every failure is typed
4. Auto-patchability — bootstraps missing schema/keys
5. Latency metrics — every operation is timed
6. Security matrix — role-based access control proof
7. Restart certification — no duplicate state, no auth corruption

---

## 8. Upgrade: ValidationHarness V2 (Modular)

The V1 monolithic harness has been refactored into a modular package:

```
atlas/validation/
  __init__.py          # Package exports
  models.py            # StageResult, Evidence, DefectType, StageStatus
  base_stage.py        # BaseStage ABC
  harness.py           # ValidationHarness orchestrator
  __main__.py          # CI entry point (exit code 1 on failure)
  cli.py               # CLI with --stage, --list-stages, --api-base
  stages/              # 10 independent stage modules
    schema_stage.py
    key_gen_stage.py
    route_stage.py
    rate_limit_stage.py
    health_stage.py
    copy_stage.py
    security_matrix_stage.py
    audit_stage.py
    restart_stage.py
    latency_stage.py
  reports/             # Report formatters
```

### Usage

```bash
# Run all stages (recommended)
python -m atlas.validation.__main__

# Run with options
python -m atlas.validation.cli --api-base http://localhost:8000 --output-dir ./reports

# Run a single stage
python -m atlas.validation.cli --stage 03_route_auth

# List available stages
python -m atlas.validation.cli --list-stages

# Legacy V1 (still works)
python scripts/day5/live_validation.py
```

## 9. Next Steps (after ValidationHarness V2)

Per strategic priority order: **Trust → Enforcement → Explainability → Deployment → Visibility → Control**

1. **Contract Governance Suite** — Route ↔ Auth ↔ Scope contract verification
2. **Event Lineage Layer** — Cross-system trace_id for full strategy lifecycle tracking
3. **CI/CD Enforcement** — GitHub Actions / deployment gates with harness as gate
4. **Dashboard** — Visibility layer on trusted infrastructure (only after governance is institutionalized)
5. **Control Plane** — Operator controls, kill switch UI, system management
