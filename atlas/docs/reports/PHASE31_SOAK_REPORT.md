# Phase 31 — Specialization Soak Report

**Generated:** 2026-05-25

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Process** | ✅ Running (PID 24788 → relaunched after fixes) |
| **Duration** | Multiple dry-runs + active soak cycles |
| **Metrics Snapshots** | 143 collected at 5-min intervals |
| **Engine Cycle Success** | ✅ 100% (all 6 engines → OK) |
| **GroupingError Status** | ✅ **RESOLVED** — no SQL errors remaining |
| **Engine Tables Populated** | 7 of 9 with data |

### Phase 31 Composite Scores (Latest)

| Score | Value | Interpretation |
|---|---|---|
| **DE** (Dominant Emergence) | **40.0** | Moderate dominant organism identification |
| **LE** (Lineage Evolution) | **37.5** | Moderate lineage tracking active |
| **RA** (Regime Adaptation) | **28.5** | Growing regime specialization awareness |
| **SD** (Scout Divergence) | **20.0** | Stable — limited scout divergence signal |
| **PE** (Portfolio Evolution) | **60.0** | Healthy evolutionary pressure detected |
| **SS** (Stress Survival) | **72.0** | Strong ecosystem stress resilience |

---

## 2. Engine Table State

| Table | Rows | Status |
|---|---|---|
| `dominant_organism_log` | 16 | ✅ Tracking active |
| `mutation_lineage_log` | 16 | ✅ Lineages tracked |
| `organism_regime_profile` | 0 | ⏳ Needs pipeline (regime-tagged backtest data) |
| `regime_specialization_aggregate` | 16 | ✅ Aggregating |
| `scout_divergence_log` | 16 | ✅ Divergence logged |
| `portfolio_evolution_log` | 16 | ✅ Pressure tracked |
| `regime_perturbation_events` | 61 | ✅ Stress events recorded |
| `execution_realism` | 0 | ⏳ Needs pipeline (execution data) |
| `phase31_specialization_metrics` | 143 | ✅ Metrics accumulating |

---

## 3. Ecosystem State (from dry-run)

| Metric | Value |
|---|---|
| Strategies Generated | 10 |
| Active / Validated Organisms | 9 |
| Trades Executed | 19 |
| Lineages Identified | 11 |
| Active Perturbations | 36 total |
| Avg Stress Survival | 72.0 |

---

## 4. Persistence Fixes Applied

### 4a. `composite_fitness_score` column
- **Status:** Column `composite_fitness_score` already existed on `backtest_results` table (NUMERIC, nullable)
- Table also includes `sortino_ratio`, `calmar_ratio`, `expectancy` columns

### 4b. `strategy_regime_performance` table — ✅ CREATED
```sql
CREATE TABLE IF NOT EXISTS strategy_regime_performance (
    id SERIAL PRIMARY KEY,
    strategy_id UUID NOT NULL,
    regime VARCHAR(50) NOT NULL,
    sharpe DOUBLE PRECISION,
    cagr DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    total_trades INTEGER,
    composite_score DOUBLE PRECISION,
    ...
);
```

### 4c. JSONB Extraction Fixes — ✅ Applied
- Extracted `total_return`, `profit_factor`, `avg_return_pct` from `results` JSONB column
- Used `CAST(results->>'field' AS DOUBLE PRECISION)` pattern

### 4d. UUID/Text Type Fixes — ✅ Applied
- Fixed `portfolio_evolution_pressure.py`: changed `fa.strategy_id::uuid` → use proper JOIN condition
- All UUID→text casts verified against actual DB schema

### 4e. GROUP BY Fixes — ✅ RESOLVED (Root Cause #2)

**Issue:** Two correlated subqueries inside aggregate contexts caused Postgres `GroupingError`:
1. `dominant_organism_tracker.py` — `_compute_mutation_family_resilience`: `m.child_strategy_id` referenced in `COUNT(*) FILTER (WHERE EXISTS (...))` subquery, but not in `GROUP BY`
2. `regime_stress_engine.py` — `_observe_stress_effects`: `strategies.id` in correlated subquery inside aggregate query without `GROUP BY`

**Fix:** Replaced both correlated subqueries with CTE (`WITH latest_fitness AS (SELECT DISTINCT ON ...)`) + `LEFT JOIN` pattern:

```sql
-- Before (broken):
SELECT COUNT(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM backtest_results br
    WHERE br.strategy_id = m.child_strategy_id      -- ❌ GroupingError
    AND br.composite_fitness_score > 30
)) AS survived_count

-- After (fixed):
WITH latest_fitness AS (
    SELECT DISTINCT ON (br.strategy_id)
        br.strategy_id, br.composite_fitness_score
    FROM backtest_results br
    ORDER BY br.strategy_id, br.created_at DESC
)
SELECT COUNT(*) FILTER (
    WHERE lf.composite_fitness_score > 30            -- ✅ No GroupingError
) AS survived_count
FROM mutation_memory m
LEFT JOIN latest_fitness lf ON lf.strategy_id = m.child_strategy_id
```

### 4f. RegimeStressEngine Persist INSERT — ✅ Fixed
- Fixed `:meta::jsonb` → `CAST(:meta AS jsonb)` for all 3 INSERT statements into `regime_perturbation_events`
- Matched actual table schema (7 columns: id SERIAL, perturbation_type, severity, started_at, status, metadata, created_at)

### 4g. ScoutDivergenceEngine — ✅ Fixed
- Fixed `composite_fitness_score FROM strategies` to use `LEFT JOIN LATERAL` to `backtest_results`
- Ensured correct fitness score extraction from backtest results per strategy

### 4h. PortfolioEvolutionPressure — ✅ Fixed
- Fixed `fa.strategy_id::uuid = s.id` type mismatch (`fa.strategy_id` is TEXT, `s.id` is UUID)
- Used proper `CAST(fa.strategy_id AS UUID)` for JOIN condition

---

## 5. Remaining Gaps

| Issue | Impact | Priority |
|---|---|---|
| `organism_regime_profile` empty | No regime-specialist organism tracking | Low — fills when pipeline runs |
| `execution_realism` empty | No execution degradation tracking | Low — fills when pipeline runs |
| Scores transition only at snapshot boundaries | Metrics may be stale between cycles | Low — expected behavior |
| No concurrent pipeline | Engine tables fill slowly without new strategy generation | Medium — run pipeline alongside |

---

## 6. Recommendations

1. **Run the main pipeline concurrently** — engines produce richer data when new strategies and backtest results are flowing through the ecosystem
2. **Monitor `regime_perturbation_events` growth** — this table tracks stress injection activity; should grow 5-15 rows per cycle
3. **Check `dominant_organism_log` content** — verify that organism identity data is being tracked correctly (strategy_id, lifespan, efficiency)
4. **Reduce metrics collection interval** from 300s to 60s for more granular score tracking during active soak

---

*Report generated from 143 metrics snapshots across 7 populated engine tables.*
