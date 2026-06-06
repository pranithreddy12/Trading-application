# POST-SOAK ANALYSIS REPORT

**Date:** 2026-05-30 08:43 UTC
**Duration:** 60-minute autonomous soak
**Status:** ✅ PASS

---

## 1. Database Health

- **Total rows across tracked tables:** 1,619,202
- **Tables verified:** 21

### Row Counts by Table

| Table | Rows |
|-------|-----:|
| backtest_trades | 1,535,210 |
| lifecycle_events | 36,039 |
| scout_signals | 16,762 |
| system_logs | 6,816 |
| pattern_memory | 6,433 |
| audit_ledger | 5,301 |
| event_store | 4,457 |
| strategies | 3,551 |
| backtest_results | 2,893 |
| feature_importance | 514 |
| drift_detection | 484 |
| failed_inserts | 364 |
| mutation_policy_state | 211 |
| execution_log | 107 |
| capital_allocation | 46 |
| paper_trades | 7 |
| copy_execution_log | 7 |
| positions | 0 |
| external_scout_memory | 0 |
| scout_quarantine | 0 |
| agent_registry | 0 |

## 2. Trading Output & Strategy Quality

- **Total backtest results:** 2893
- **Scored:** 2893
- **Avg Short Window Score:** 29.13
- **Avg Sharpe:** 13.24
- **Avg Win Rate:** 13.19%

### Top 10 Strategies

| # | Name | Score | Sharpe | Win Rate |
|---|------|:----:|:------:|:--------:|
| 1 | volatility_regime_equity_det_101354 | 41.00 | 282.69 | 57.89% |
| 2 | volatility_regime_equity_det_101345 | 39.10 | 263.72 | 53.33% |
| 3 | volatility_regime_equity_det_180729 | 39.10 | 0.00 | 53.33% |
| 4 | volatility_regime_equity_det_191958 | 38.40 | 0.00 | 51.52% |
| 5 | volatility_regime_equity_det_201055 | 37.90 | 0.00 | 50.00% |
| 6 | volatility_regime_equity_det_172120 | 37.70 | 0.00 | 50.00% |
| 7 | volatility_regime_equity_det_173009 | 37.60 | 0.00 | 50.00% |
| 8 | momentum_equity_det_171011_71 | 37.50 | 0.00 | 48.72% |
| 9 | momentum_equity_det_173946_67 | 37.50 | 0.00 | 48.72% |
| 10 | momentum_equity_det_171741_69 | 37.50 | 0.00 | 48.72% |

## 3. Execution & Copy-Trading

- **Paper trades:** 7
- **Total PnL:** 0.00
- **Copy execution entries:** 7

## 4. Scout Network

- **Scout signals:** 16762
- **External scout entries:** 0
- **Quarantined scouts:** 0

## 5. Hash Chain Integrity

- **Event store:** 4457 events, 4457 hashed
- **Audit ledger:** 5301 entries, 5301 hashed

## 6. Dead-Letter Queue

- **Failed inserts:** 364

### Failed Inserts Breakdown

| Table | Reason | Count |
|-------|--------|:----:|
| feature_importance | zero_rowcount | 114 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| system_logs | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| system_logs | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |
| economic_fitness_windows | (sqlalchemy.dialects.postgresql.asyncpg.Error) <cl | 1 |

## 7. Agent Lifecycle

- **Agent starts:** 23139
- **Agent stops:** 0
- **Agent crashes:** 0
- **Unique agents:** 14

## 8. Summary

- **Checks passed:** 7
- **Checks failed:** 0
- **Warnings:** 1

>>> **CERTIFIED FOR DELIVERY** <<<
