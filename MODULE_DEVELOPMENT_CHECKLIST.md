# MODULE DEVELOPMENT CHECKLIST

**Use this before shipping any new feature/service/API endpoint**

---

## PRE-BUILD: ARCHITECTURE DESIGN

**Before writing code, answer:**

- [ ] What domain layer does this belong in? (L1-L7 + API/Dashboard)
- [ ] What service(s) will this use/create?
- [ ] What data does this create/modify?
- [ ] What events should this emit?
- [ ] Who should have access? (RBAC roles)
- [ ] What could go wrong? (Failure modes)
- [ ] How do we restart after crash? (Idempotency plan)
- [ ] How do we know it's working? (Observability points)

---

## DATA LAYER

**Database changes:**

- [ ] Migration file created (scripts/migrations/XXX_*.sql)
- [ ] Uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
- [ ] Includes audit columns (created_at, updated_at, created_by)
- [ ] Includes status enum column (not bare boolean)
- [ ] Includes indexes on foreign keys and common filters
- [ ] Comments on non-obvious columns
- [ ] Soft-delete support where meaningful
- [ ] Version column for optimistic locking (if concurrent updates)

**State machine:**

- [ ] Status column uses enum CHECK constraint
- [ ] Explicit states defined (draft, validating, validated, etc.)
- [ ] Transitions documented in code comments
- [ ] Invalid transitions prevented (DB-side or service-side)

---

## SERVICE LAYER

**Business logic:**

- [ ] Service class created (e.g., CopyService, RiskService)
- [ ] Pure functions where possible (no side effects)
- [ ] All DB access goes through service
- [ ] Transactional operations use db.transaction()
- [ ] Proper error handling with typed exceptions
- [ ] Logging at key decision points
- [ ] Tests exist for service (unit tests)

**Idempotency:**

- [ ] Idempotency guard implemented (check exists before insert)
- [ ] Atomic DB transaction wraps mutation
- [ ] Retry-safe logic (no partial state on crash)
- [ ] Restart scenario documented

---

## EVENT LAYER

**Important events:**

- [ ] Event types defined (as dataclass/enum)
- [ ] Event emitted on state change
- [ ] Events logged to database
- [ ] Events contain: (entity_type, action, data, timestamp, actor, reason)
- [ ] Event stream can be replayed for debugging
- [ ] Old events can be archived

---

## SECURITY LAYER

**Access control:**

- [ ] API endpoints require authentication
- [ ] Permission checks against RBAC roles
- [ ] Sensitive actions require specific roles (not just "authenticated")
- [ ] Action logged to audit_logs table
- [ ] Rate limit applied (per endpoint, per key)
- [ ] Secrets not hardcoded (use settings/.env)

**If data mutation:**

- [ ] User ID/API key ID captured (created_by)
- [ ] Action reason captured (why was this changed?)
- [ ] Timestamp recorded
- [ ] Audit entry immutable (never deleted)

---

## API LAYER

**Endpoint design:**

- [ ] Route path follows RESTful convention
- [ ] HTTP method correct (GET, POST, PUT, DELETE)
- [ ] Request validation (Pydantic model)
- [ ] Response schema defined
- [ ] Error responses typed (400, 401, 403, 404, 500)
- [ ] Rate limit header included
- [ ] Latency measured and returned in response

**If read endpoint:**

- [ ] Pagination support (limit, offset)
- [ ] Filtering support (status, date_range, etc.)
- [ ] Sorting support
- [ ] Only authorized data returned

**If write endpoint:**

- [ ] Input validation thorough
- [ ] Risk checks applied (before mutation)
- [ ] Idempotency key support (optional, but good)
- [ ] Soft-delete semantics correct
- [ ] Response includes created/updated record

---

## TESTING LAYER

**Unit tests:**

- [ ] Service logic tested independently
- [ ] Edge cases covered
- [ ] Failure modes tested
- [ ] Mocked dependencies used

**Integration tests:**

- [ ] Service + database tested together
- [ ] Real DB (in-memory for tests)
- [ ] Transactions rollback correctly
- [ ] Data constraints enforced

**Smoke tests:**

- [ ] Happy path works end-to-end
- [ ] API can be called successfully
- [ ] Response data is correct

**Restart tests (if mutation):**

- [ ] Crash simulated mid-execution
- [ ] Service restarted
- [ ] No duplicate mutations applied
- [ ] State is consistent

**Contract tests:**

- [ ] API count matches DB count
- [ ] API filtering matches DB query
- [ ] Prevent silent drift

---

## OBSERVABILITY LAYER

**Health checks:**

- [ ] Service contributes to /health endpoint
- [ ] Can report: healthy, warning, critical
- [ ] Latency measured
- [ ] Dependencies checked

**Metrics:**

- [ ] Success/failure counted
- [ ] Latency tracked (p50, p99)
- [ ] Throughput measured
- [ ] Errors categorized

**Logging:**

- [ ] Important decisions logged
- [ ] Failures logged with full context
- [ ] Structured logging (key-value pairs, not free text)
- [ ] Correlation ID included (for request tracing)

---

## SCALABILITY LAYER

**Future-proofing:**

- [ ] Will this work at 10x load?
- [ ] Are there bottlenecks?
- [ ] Can this be distributed?
- [ ] Is this horizontally scalable?
- [ ] Connection pools sized correctly?

---

## DOCUMENTATION LAYER

**For other developers:**

- [ ] README or docstring explains what this does
- [ ] State diagram included (if stateful)
- [ ] Example API calls provided
- [ ] Error conditions documented
- [ ] Deployment notes included
- [ ] Rollback plan documented

---

## FINAL CHECKLIST

**Before shipping, verify:**

- [ ] Code review completed
- [ ] All tests passing
- [ ] Linter/formatter clean
- [ ] No hardcoded secrets
- [ ] No console logs (use logging)
- [ ] Error handling not silent
- [ ] Documentation complete
- [ ] Rollback procedure tested
- [ ] Monitoring alerts in place
- [ ] Feature can be toggled off

---

## QUALITY GATE QUESTIONS

**Answer these before merging:**

```
✓ Does this improve trust, resilience, control, or scalability?
✓ Can this survive a crash?
✓ Is this observable?
✓ Is this maintainable?
✓ Will this still make sense at 10x load?

If any answer is "No" → Rework before shipping
```

---

**Use this checklist for every feature from Day 5 onward.**

**This is the difference between startup code and platform code.**
