# DAY 5 Phase A Audit

## Scope

This audit validates that AuthService governs live API behavior, not only service-isolated tests.

## Changes Applied

1. Integrated AuthService + AuthMiddleware into the live Day 4 API runtime.
2. Replaced legacy shared-token path with role-aware key validation.
3. Enforced scope checks on protected routes.
4. Added centralized request audit logging middleware.
5. Added rate-limit governance dependency with role-aware quotas and response headers.
6. Added contract-friendly service extractions for copy and risk reads.

## Schema Rollout

Apply auth schema with:

```powershell
psql $env:DATABASE_URL -f scripts/migrations/day5_auth_schema.sql
```

If using docker-compose service:

```powershell
docker compose exec -T db psql -U postgres -d atlas -f /workspace/scripts/migrations/day5_auth_schema.sql
```

## Real Role Key Generation

Generate one real key per role:

```powershell
python scripts/day5/generate_role_keys.py
```

Expected output: JSON object with keys for admin, trader, read_only, follower, monitor.

## Protected Route Enforcement

Governed routes now include:

- GET /health
- GET /copy/logs
- GET /leaders
- GET /followers
- GET /portfolio
- GET /risk
- GET /strategies
- GET /status
- GET /copy/status

All governed requests flow through:

- AuthMiddleware token validation
- Scope enforcement
- RateLimitService quota enforcement
- Request audit logging

## Permission Matrix and Failure-Mode Tests

Implemented in:

- scripts/tests/day5/test_auth_integration.py

Coverage includes:

- Role matrix permissions
- Missing auth header failure path
- Rate-limit deny behavior
- Audit logging invocation
- Governance latency budget (<500ms check)

## Audit Log Tests

Request logging is centralized in API middleware and emits into api_request_audit through AuthService.log_request.

## Latency Test

Governance path latency test is included in test_auth_integration.py via limiter path timing assertion.

## Result

Phase A auth governance is now integrated into live API routing, instrumented, and test-covered for core enforcement behavior.
