# DAY 6 — Schema Migration Certification

## Temporal Governance + Combination Governance — Data Layer Certification

---

### PHASE A — Environment Verification

| Component | Status | Container | Host Port |
|-----------|--------|-----------|-----------|
| TimescaleDB | `healthy` | `atlas_timescaledb` | 5433 |
| Redis | `healthy` | `atlas_redis` | 6380 |

**Result: PASS**

---

### PHASE B — Pre-Migration Audit

| Check | Result |
|-------|--------|
| Existing tables | 22 tables present (`strategies`, `backtest_results`, `mutation_memory`, etc.) |
| `backtest_results` columns | 13 columns — NO short_window fields |
| `combination_memory` | Does NOT exist |
| Strategies count | 47 total (39 `pending_validation`, 8 `code_failed`) |
| Backtest results count | 39 rows |
| Backup created | `pre_day6_temporal_backup.sql` (pg_dump, container → host) |

**Result: PASS**

---

### PHASE C — Migration Applied

#### 1. `backtest_results` — Added temporal governance columns

```sql
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS short_window_score NUMERIC;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS score_7d NUMERIC;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS score_14d NUMERIC;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS score_30d NUMERIC;
```

**Result: 4 columns added (17 total)**

#### 2. `combination_memory` — Created combination governance table

```sql
CREATE TABLE IF NOT EXISTS combination_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_a UUID NOT NULL REFERENCES strategies(id),
    parent_b UUID NOT NULL REFERENCES strategies(id),
    child_id UUID REFERENCES strategies(id),
    combination_type TEXT NOT NULL,
    parent_a_sharpe NUMERIC,
    parent_b_sharpe NUMERIC,
    child_sharpe NUMERIC,
    sharpe_delta NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(parent_a, parent_b, combination_type)
);
CREATE INDEX idx_combination_memory_parent_a ON combination_memory (parent_a);
CREATE INDEX idx_combination_memory_parent_b ON combination_memory (parent_b);
CREATE INDEX idx_combination_memory_child ON combination_memory (child_id);
```

**Result: Table created with 5 indexes (1 PK, 1 UNIQUE, 3 B-tree)**

#### 3. `schema.sql` — Updated to reflect both additions

**Result: schema.sql now includes `combination_memory` table and short_window columns**

---

### PHASE D — Post-Migration Validation

| Object | Field/Index | Status |
|--------|------------|--------|
| `combination_memory` | `id` (UUID PK) | ✓ |
| `combination_memory` | `parent_a` (UUID FK → strategies) | ✓ |
| `combination_memory` | `parent_b` (UUID FK → strategies) | ✓ |
| `combination_memory` | `child_id` (UUID FK → strategies, nullable) | ✓ |
| `combination_memory` | `combination_type` (TEXT NOT NULL) | ✓ |
| `combination_memory` | `parent_a_sharpe` (NUMERIC) | ✓ |
| `combination_memory` | `parent_b_sharpe` (NUMERIC) | ✓ |
| `combination_memory` | `child_sharpe` (NUMERIC) | ✓ |
| `combination_memory` | `sharpe_delta` (NUMERIC) | ✓ |
| `combination_memory` | `created_at` (TIMESTAMPTZ DEFAULT NOW()) | ✓ |
| `combination_memory` | UNIQUE(parent_a, parent_b, combination_type) | ✓ |
| `backtest_results` | `short_window_score` (NUMERIC) | ✓ |
| `backtest_results` | `score_7d` (NUMERIC) | ✓ |
| `backtest_results` | `score_14d` (NUMERIC) | ✓ |
| `backtest_results` | `score_30d` (NUMERIC) | ✓ |

**Result: PASS**

---

### PHASE E — Governance Smoke Test

| Test | Result |
|------|--------|
| Insert dummy combination row | ✓ — Row created with UUID |
| Verify row exists | ✓ — SELECT returns row |
| UNIQUE constraint enforces dedup | ✓ — Duplicate insert raises `unique_violation` |
| Clean up test row | ✓ — DELETE succeeds |

**Result: PASS**

---

## FINAL CERTIFICATION

```
Temporal Governance Schema:  CERTIFIED
Combination Governance Schema: CERTIFIED
Operational Schema:           CERTIFIED
```

### Database is now ready for:

- **Priority 2:** `batch_reprocess_all.py` — recompute ecosystem under temporal governance
- **Priority 3:** `control_strategy_benchmark.py` — verify known-good strategies maintain recent viability
- **Priority 4:** Combiner smoke test — validate governed synthesis with `combination_memory`
- **Priority 5:** `temporal_governance_check.py` validation harness

### Blockers: None

### Next action: Begin Priority 2 — Batch reprocess
