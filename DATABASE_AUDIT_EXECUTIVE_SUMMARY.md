# DATABASE AUDIT: EXECUTIVE SUMMARY & ACTION PLAN

**Date:** May 18, 2026  
**Database:** ATLAS (TimescaleDB + PostgreSQL)  
**Status:** Operational but Fragile (5.58/10 maturity)  
**Risk Level:** MEDIUM-HIGH

---

## CRITICAL FINDINGS AT A GLANCE

### 🔴 RED ALERTS (Deploy This Week)

#### 1. **Precision Crisis**
- ⚠️ All NUMERIC columns store unbounded precision
- ❌ No CHECK constraints enforcing 4-6 decimal rounding
- 🚨 **Risk:** Backtests calculate Sharpe based on imprecise data; silent float errors accumulate
- **Fix:** Phase1_schema_hardening.sql — add CHECK constraints (30 min deployment)

#### 2. **No Uniqueness Enforcement**
- ⚠️ market_data_l1 can have duplicate (time, symbol) bars
- ⚠️ execution_log can log same order_key twice
- ⚠️ copy_execution_log can duplicate (leader_order_id, follower_id)
- 🚨 **Risk:** Re-ingestion causes stale features_wide; duplicate orders placed
- **Fix:** Add UNIQUE constraints in Phase 1 (10 min)

#### 3. **Missing Foreign Keys**
- ⚠️ backtest_results → strategies: NO FK (orphans possible)
- ⚠️ backtest_trades → strategies: NO FK (orphans possible)
- ⚠️ performance_metrics → strategies: NO FK (orphans possible)
- 🚨 **Risk:** Delete strategy but backtest/trade records remain; data consistency violation
- **Fix:** Add FK with CASCADE DELETE in Phase 1 (15 min)

#### 4. **Type Mismatch in Lineage**
- ⚠️ lifecycle_events.strategy_id: TEXT vs strategies.id: UUID
- 🚨 **Risk:** Event lineage link breaks; trace corruption possible
- **Fix:** Alter type in Phase 1.5 (45 min, requires validation)

#### 5. **No Atomic Transactions**
- ⚠️ order fill and position update are separate SQL statements
- 🚨 **Risk:** Crash between insert/update leaves stale position; risk checks fail
- **Fix:** Wrap in transaction at application level (URGENT code review)

---

### 🟡 YELLOW ALERTS (Deploy Next 2 Weeks)

#### 6. **Missing Indexes on Hot Paths**
- ❌ No index on market_data_l1.symbol (frequent filter)
- ❌ No index on strategies.created_at (rank by date)
- ❌ No index on backtest_results.sharpe (ranking queries)
- 🚨 **Risk:** Dashboard/ranking queries timeout; ingestion slowdown
- **Fix:** Phase2_enum_and_indexes.sql — add 15+ indexes (1 hour deployment)

#### 7. **Enum Validation Missing**
- ❌ side ("buy", "sell") not validated
- ❌ state ("pending", "filled", etc.) not validated
- ❌ status values not validated
- 🚨 **Risk:** Invalid values silently stored; queries break
- **Fix:** Add CHECK constraints in Phase 2 (30 min)

#### 8. **Stale Data Risks**
- ⚠️ features_wide manually refreshed (staleness gap possible)
- ⚠️ agent_registry.last_heartbeat stale after crash (no cleanup)
- ⚠️ intelligence_briefs outdated (no versioning)
- 🚨 **Risk:** Dashboard shows stale/false data; decisions on bad data
- **Fix:** Monitoring view in Phase 2 + alerting (2 hours)

#### 9. **Dead Letter Queue Accumulation**
- ⚠️ execution_dead_letter requires manual review
- ⚠️ No auto-cleanup; could accumulate indefinitely
- 🚨 **Risk:** Operational debt; missed critical failures
- **Fix:** Alerting + runbook in Phase 2 (1 hour)

#### 10. **Position/Order Divergence**
- ⚠️ copy_trader checks positions from stale rows
- ❌ No constraint linking order fill + position update
- 🚨 **Risk:** Risk checks fail; position allocation broken
- **Fix:** Create v_order_position_mismatch view in Phase 2; enforce at app level

---

## SCOPE: ALL 27 TABLES AUDITED

### Tier 1: Time-Series (Critical)
| Table | Issue | Severity | Fix |
|-------|-------|----------|-----|
| market_data_l1 | Unbounded precision, no uniqueness | 🔴 HIGH | Phase 1 |
| market_data_l2 | No JSONB validation, stale spread data | 🟡 MEDIUM | Phase 2 |
| order_flow | No side validation, duplicates possible | 🟡 MEDIUM | Phase 2 |
| features | feature_name not validated, multiple values per key | 🟡 MEDIUM | Phase 2 |
| features_wide | Stale after ingestion, CONCURRENTLY refresh | 🟡 MEDIUM | Phase 2 |
| system_logs | Good append-only, but no level validation | 🟢 LOW | Phase 2 |
| performance_metrics | No metric_name validation | 🟢 LOW | Phase 2 |
| paper_trades | Low criticality, side/status not validated | 🟢 LOW | Phase 2 |

### Tier 2: Catalog (High Priority)
| Table | Issue | Severity | Fix |
|-------|-------|----------|-----|
| strategies | Status not validated, no created_at index | 🟡 MEDIUM | Phase 2 |
| backtest_results | No FK, no sharpe index | 🔴 HIGH | Phase 1+2 |
| backtest_trades | No FK, no symbol index | 🔴 HIGH | Phase 1+2 |
| intelligence_briefs | Stale regime, no freshness guarantee | 🟢 LOW | Phase 2 |
| mutation_memory | Good FK, needs mutation_type index | 🟡 MEDIUM | Phase 2 |
| combination_memory | Good design, needs combination_type index | 🟡 MEDIUM | Phase 2 |
| lifecycle_events | Type mismatch (strategy_id TEXT vs UUID) | 🔴 HIGH | Phase 1.5 |
| pattern_memory | Auto-migrated, no dedup | 🟡 MEDIUM | Phase 2 |

### Tier 3: Execution (Critical)
| Table | Issue | Severity | Fix |
|-------|-------|----------|-----|
| execution_log | No order_key uniqueness, state not validated | 🔴 HIGH | Phase 1+2 |
| execution_dead_letter | Manual resolution, no auto-cleanup | 🟡 MEDIUM | Phase 2 |
| positions | No (account, symbol) uniqueness, stale data | 🔴 HIGH | Phase 1+2 |
| copy_execution_log | No uniqueness, status not validated | 🔴 HIGH | Phase 1+2 |

### Tier 4: Operational (Security/Audit)
| Table | Issue | Severity | Fix |
|-------|-------|----------|-----|
| api_keys | Role validation needed | 🟡 MEDIUM | Phase 2 |
| api_request_audit | Good structure, needs endpoint index | 🟡 MEDIUM | Phase 2 |
| audit_logs | Status validation needed | 🟡 MEDIUM | Phase 2 |
| agent_registry | Stale agents never cleaned | 🟡 MEDIUM | Phase 2 |

---

## PHASE-WISE ACTION PLAN

### PHASE 1: CRITICAL (This Week - May 18-22)
**Effort:** 16 hours | **Risk:** Low | **Impact:** High

#### Steps:
1. **Backup database** (30 min)
   ```bash
   pg_dump -h localhost -p 5433 -U postgres -d atlas > atlas_backup_20260518.sql
   ```

2. **Test Phase 1 migration in staging** (2 hours)
   ```bash
   psql < phase1_schema_hardening.sql
   ```

3. **Validate no constraint violations** (1 hour)
   - Query for precision violations (should be 0)
   - Query for duplicate (time, symbol) in market_data_l1 (should be 0)
   - Query for orphaned backtest_results (should be 0)

4. **Deploy Phase 1 to production** (1 hour)
   - Off-peak deployment (2am-4am)
   - Run phase1_schema_hardening.sql
   - Verify constraints applied

5. **Fix application code for atomic transactions** (4 hours)
   - Wrap order insert + position update in `engine.begin()` transaction
   - Code review on copy_trader._log_copy_execution()

6. **Test Phase 1 deployment** (4 hours)
   - Manual ingestion test
   - Copy trader test
   - Backtest test

7. **Monitoring setup** (2 hours)
   - Set up alerting for constraint violations
   - Dashboard for failed inserts

#### Files to Deploy:
- `scripts/migrations/phase1_schema_hardening.sql`
- Updated `copy_trader.py` (atomic transactions)

---

### PHASE 1.5: TYPE MIGRATION (May 22-23)
**Effort:** 2-3 hours | **Risk:** Medium (requires validation) | **Impact:** High

#### Steps:
1. **Backup** (10 min)
2. **Convert strategy_id to UUID** (30 min)
   ```sql
   ALTER TABLE lifecycle_events
     ALTER COLUMN strategy_id TYPE UUID USING (strategy_id::UUID);
   ```
3. **Add FK constraint** (10 min)
4. **Validate no broken links** (30 min)
5. **Test** (1 hour)

---

### PHASE 2: HIGH-PRIORITY (Week of May 25)
**Effort:** 24 hours | **Risk:** Low-Medium | **Impact:** Medium

#### Steps:
1. **Deploy Phase 2 SQL** (2 hours)
   - phase2_enum_and_indexes.sql
   - 15+ new indexes
   - enum CHECK constraints
   - data quality view

2. **Test index performance** (3 hours)
   - Backtest ranking query (should be 5-10x faster)
   - Symbol filtering (should be 10-50x faster)
   - Ingestion latency (should be <5% slower)

3. **Deploy alerting** (4 hours)
   - Daily audit queries (see DATABASE_AUDIT_REPORT.md)
   - Slack alerts for:
     - Orphaned records
     - Stale agents
     - Dead letter backlog
     - Precision violations
     - Type mismatches

4. **Create runbooks** (6 hours)
   - Duplicate data recovery
   - Position/order mismatch recovery
   - Stale feature refresh
   - Dead letter manual review

5. **Dashboard updates** (4 hours)
   - Show data quality summary
   - Alert on stale data
   - Highlight unresolved dead letters

6. **Documentation** (5 hours)
   - Update schema docs
   - Add data integrity guide
   - Recovery procedures

#### Files to Deploy:
- `scripts/migrations/phase2_enum_and_indexes.sql`
- New monitoring/alerting (TODO: create)
- Runbooks (TODO: create)

---

### PHASE 3: NICE-TO-HAVE (Following Sprint)
**Effort:** 20+ hours | **Risk:** Low | **Impact:** Low-Medium

1. **Generate columns for derived metrics**
   - positions.market_value = qty * avg_price
   - backtest_trades.pnl_bps = pnl_pct * 10000

2. **Background refresh for features_wide**
   - Async job instead of manual
   - Versioning for staleness detection

3. **Dedup detection for pattern_memory**
   - UNIQUE constraint on (pattern_type, archetype, feature_family)
   - Auto-merge duplicates

4. **Data archival strategy**
   - Move old market_data to separate schema
   - Partition by month/year
   - Reduce query scope

---

## RISK ASSESSMENT

### What Could Go Wrong in Phase 1?

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Constraint conflict on existing data | LOW | MEDIUM | Test in staging first; analyze for violations |
| Performance regression (indexes) | MEDIUM | MEDIUM | Phase indexes separately; monitor query times |
| Rollback required | LOW | LOW | Have rollback scripts ready; test them |
| Data loss from CASCADE DELETE | VERY LOW | HIGH | Backup first; verify orphans minimal before deploy |

### Mitigation Strategy:
1. ✅ Backup before any schema changes
2. ✅ Test every migration in staging first
3. ✅ Dry-run on production clone if possible
4. ✅ Have rollback scripts ready
5. ✅ Monitor performance before/after
6. ✅ Staged rollout: test table first, then prod

---

## RESOURCE REQUIREMENTS

### Personnel:
- **DBA:** 1-2 hours per phase for deployment/monitoring
- **Backend Engineer:** 4-6 hours per phase for code changes + testing
- **DevOps:** 2-3 hours for backup/recovery setup

### Tools:
- PostgreSQL 12+
- pg_dump for backups
- psql for migrations
- Monitoring: Prometheus/Grafana (optional but recommended)

### Timeline:
- Phase 1: May 18-22 (5 days)
- Phase 1.5: May 22-23 (2 days)
- Phase 2: May 25-31 (1 week)
- **Total: 2 weeks to operational excellence**

---

## SUCCESS CRITERIA

### After Phase 1 Deployment:
- ✅ All UNIQUE constraints applied without error
- ✅ All FK constraints applied; CASCADE delete tested
- ✅ No precision violations in existing data
- ✅ Atomic transactions wrap order+position updates
- ✅ Ingestion latency <10% increase
- ✅ All tests pass (backtest, copy trader, feature calc)

### After Phase 2 Deployment:
- ✅ 15+ new indexes created; queries 5-50x faster
- ✅ All enum CHECK constraints applied
- ✅ Data quality view shows FRESH status
- ✅ Alerting active for orphans/stale data
- ✅ Runbooks documented and tested

### Final Maturity Score:
- **Current:** 5.58/10
- **Target:** 7.5/10 (after Phase 1+2)
- **Metrics:**
  - Schema clarity: 6 → 8
  - Data integrity: 4.71 → 7.5
  - Auditability: 6.33 → 8
  - Recovery: 5.9 → 8
  - Production readiness: 5.05 → 7.5

---

## DEPENDENCIES & BLOCKERS

### Must Deploy Before Phase 1:
- ✅ Latest backup strategy
- ✅ Staging environment synced to production

### Must Deploy Before Phase 2:
- ✅ Phase 1 complete
- ✅ Application code updated for atomic transactions

### Known Issues to Address First:
- ❌ Are there real data precision violations in production? (Need audit query)
- ❌ How many orphaned backtest_results exist? (Need count)
- ❌ Any existing (time, symbol) duplicates in market_data_l1? (Need count)

**Action:** Run diagnostic queries in ATLAS_DIAGNOSTIC.sql (TODO: create)

---

## COMMUNICATION PLAN

### Stakeholders to Notify:
1. **Engineering Lead** — Timeline, deployment window
2. **Product** — No feature impact; backend hardening only
3. **Operations** — Monitor during deployment; rollback if needed
4. **Data Scientists** — Backtest performance may improve (good news)

### Messaging:
- "Database hardening sprint to improve reliability"
- "No API changes; transparent upgrade"
- "Improves data consistency and query performance"

### Deployment Window:
- **Phase 1:** Saturday 2am-5am (off-peak)
- **Phase 2:** Next Sunday 2am-5am

---

## NEXT STEPS

1. **TODAY (May 18):** Review this document; approve phases
2. **TOMORROW (May 19):** Create diagnostic queries; measure current state
3. **MON (May 20):** Test Phase 1 in staging; prepare rollback scripts
4. **WED (May 22):** Deploy Phase 1 (Saturday night)
5. **MON (May 25):** Deploy Phase 2 (Sunday night)
6. **ONGOING:** Monitor alerts; execute runbooks as needed

---

## APPENDIX: QUICK REFERENCE

### Key Files:
- **Main Audit:** `DATABASE_AUDIT_REPORT.md`
- **Phase 1 SQL:** `scripts/migrations/phase1_schema_hardening.sql`
- **Phase 2 SQL:** `scripts/migrations/phase2_enum_and_indexes.sql`
- **Diagnostics:** TODO
- **Runbooks:** TODO

### Contact:
- **DBA on-call:** [Name] — for deployment questions
- **DevOps:** [Name] — for backup/recovery
- **Backend Lead:** [Name] — for application changes

---

**Report Prepared By:** Database Audit Agent  
**Approval Required By:** Engineering Lead  
**Implementation Target:** Week of May 18, 2026
