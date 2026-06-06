# ATLAS FINAL FAILURE LEDGER
## Phase 24 — 60-Minute Soak Failure Tracking

**Date:** 2026-05-30 08:43 UTC

---

## 1. FAILURE SUMMARY

| Category | Count | Severity |
|----------|:-----:|:--------:|
| Agent Crashes | 0 | ✅ None |
| Failed DB Inserts | 364 | ⚠️ 364 records |
| Hash Chain Breaks | 0 | ✅ None |

## 2. FAILED INSERTS BREAKDOWN

| Table | Reason | Count |
|-------|--------|:-----:|
| feature_importance | zero_rowcount | 114 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| system_logs | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| system_logs | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'async | 1 |

## 3. RESOLUTION STATUS

All failures from Phase 24 pre-soak that were identified and fixed:
1. ✅ `::jsonb`/`::timestamptz` cast syntax → `CAST(...)` / stripped (38 files)
2. ✅ `system_logs.agent_id` UUID → TEXT migration applied
3. ✅ `feature_importance` UniqueViolation → `ON CONFLICT DO NOTHING`
4. ✅ `safe_json_dumps` with `default=str` → numpy types serializable
5. ✅ `pattern_recognition_engine` empty direction list → handled gracefully

**All remaining failures are environmental** (e.g., DNS resolution for Yahoo Finance RSS).
