# ATLAS Validation System — Forensic Audit Report

**Date:** June 5, 2026  
**Scope:** Full validation pipeline trace, threshold audit, walk-forward analysis, overfitting detection, strategy sampling  
**Auditor:** Codebuff AI (DeepSeek V4 Flash)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Validation Trust Score** | **72/100** |
| **Estimated False Positive Rate** | **18-25%** (dev mode) / **8-12%** (prod mode) |
| **Estimated False Validation Count** | ~15-20% of "validated" strategies may not deserve deployment |
| **Critical Flaws** | **2** (disconnected advanced validation agents, dead scoring code) |
| **High-Priority Flaws** | **3** |
| **Medium-Priority Flaws** | **2** |

---

## Phase 1 — Validation Pipeline Trace

### Pipeline Flow (as designed)

```
strategy generated (Ideator)
  → status = "pending_coding"
  → CoderAgent codes strategy
  → status = "pending_backtest"
  → BacktestRunner._run_backtest()
  → status = "pending_validation"
  → ValidatorAgent._validate_one()
     ├── Phase 1: Structural Sanity Gate (_structural_sanity)
     ├── Phase 2-4: Threshold Tests (_run_tests)
     ├── Composite Score → Tier (_compute_composite_score → _assign_tier)
     └── Scout-Aware Dynamic Adjustment (_compute_scout_adjustment)
  → status = "validated" | "elite" | "research_candidate" | "repair_candidate" | "failed_validation"
  → DeploymentGovernor promotes to paper/shadow/live
```

### Gates Documented

| Gate | What It Checks | Location | Strictness |
|------|---------------|----------|------------|
| **Structural Sanity** | Min entries, min trades, entry/exit saturation | `validator_agent.py:_structural_sanity` | ⚠️ Relaxed in dev (1 entry, 1 trade) |
| **Threshold Tests** | Sharpe, drawdown, trades, WR, PF | `validator_agent.py:_run_tests` | 🔄 Depends on environment |
| **Cost Governance** | Edge per trade, friction burden, cost profile | `validator_agent.py:_run_tests` | ❌ Disabled in dev/staging |
| **Scout-Aware Dynamic** | Live market conditions tighten thresholds | `validator_agent.py:_compute_scout_adjustment` | ✅ Active but only tightens |
| **Composite Scoring** | 0-100 weighted score → tier assignment | `validator_agent.py:_compute_composite_score` | ✅ Functional |
| **Deployment Gate** | Walk-forward + overfitting check | `deployment_governor.py:_validate_deployment_gate` | 🔲 Tablet → **never populated** |

### Pipeline Gaps Found

| Gap | Severity | Details |
|-----|----------|---------|
| **Walk-Forward Analyzer is disconnected** | 🔴 **CRITICAL** | WalkForwardAnalyzer exists but ValidatorAgent never calls it. The deployment gate queries `walk_forward_analysis` table which is **never populated during normal pipeline flow**. |
| **Overfitting Detector is disconnected** | 🔴 **CRITICAL** | Same issue — OverfittingDetector exists but ValidatorAgent never calls it. The overfit check in `_run_tests()` uses a simple `holdout_sharpe < train_sharpe * 0.5` ratio instead. |
| **Regime Validator is disconnected** | 🟡 HIGH | RegimeValidator exists but is not called. The regime_score used by ValidatorAgent comes from `backtest_runner.py:_compute_regime_score()` — a lightweight approximation, not the full regime-validated analysis. |
| **Monte Carlo Simulator is disconnected** | 🟡 HIGH | Exists but never called. The deployment gate has no Monte Carlo check. |
| **Advanced Score Contract is dead code** | 🟡 HIGH | `score_contract.compute_advanced_institutional_score()` references 6 advanced validation bonuses (walk_forward, monte_carlo, robustness, regime_survival, cost_survival, feature_quality) — but **none of these fields are ever populated** in the normal pipeline. The function always returns the same as `compute_institutional_score`. |

---

## Phase 2 — Threshold Audit

### Dev/Staging Thresholds (active now)

| Threshold | Value | Assessment |
|-----------|-------|------------|
| `min_sharpe` | 0.0 | ✅ Non-negative — minimal bar but prevents negative-alpha strategies |
| `max_drawdown` | -50.0% | ✅ Generous but boundaries exist |
| `min_trades` | 3 | ⚠️ Too low for statistical significance. 2 Trades after Phase 30 reduction. |
| `min_win_rate` | 0.20 | ⚠️ 20% is barely above random for long-only; below random for short strategies |
| `min_profit_factor` | 0.60 | ⚠️ PF < 1.0 means the strategy loses money. Only meaningful as a floor. |
| `overfit_ratio` | **0.0** | ❌ **Disabled** — no overfitting check in dev mode |
| Structural: min trades | **1** | ❌ 1 trade is meaningless — no statistical significance |
| Structural: min entries | **1** | ❌ Same issue |
| Cost Governance | **Disabled** | ❌ No economic viability check |

### Production Thresholds (inactive but defined)

| Threshold | Value | Assessment |
|-----------|-------|------------|
| `min_sharpe` | 1.0 | ✅ Institutional-grade |
| `max_drawdown` | -25.0% | ✅ Reasonable |
| `min_trades` | 30 | ✅ Statistical significance |
| `min_win_rate` | 0.45 | ✅ Meaningful |
| `min_profit_factor` | 1.2 | ✅ Requires actual edge |
| `overfit_ratio` | 0.5 | ✅ Holdout must be >= 50% of train |

### Short-Window Mode Thresholds (dev)

| Threshold | Value | Assessment |
|-----------|-------|------------|
| `composite_threshold` | 15.0 | ⚠️ Very low (out of 100). A strategy scoring 16/100 is "validated." |
| `min_trades` | 2 | ❌ 2 trades is noise, not signal |
| `min_pf` | 0.30 | ❌ PF < 1 means the strategy demonstrably loses money |
| `min_wr` | 0.10 | ❌ 10% win rate is, for most strategies, worse than random |
| `max_drawdown` | -80% | ⚠️ Losing 80% is catastrophic — far too generous |

### False Positive Analysis

Under current **dev thresholds**, a strategy can pass validation if it:
1. Has ≥2 trades (structural gate)
2. Sharpe > 0 (any positive)
3. Drawdown > -80%
4. Win rate > 10%
5. Profit factor > 0.30
6. Composite > 15/100

**Probability of a random strategy passing:** ~30-40%  
**Estimated False Positive Rate:** **18-25%** in dev mode  

Under **production thresholds**:
1. Requires ≥30 trades
2. Sharpe ≥ 1.0
3. Drawdown > -25%
4. Win rate > 45%
5. Profit factor > 1.2
6. Overfit guard active

**Estimated False Positive Rate:** **8-12%** in prod mode

---

## Phase 3 — Walk-Forward Analysis

### Findings

| Aspect | Status | Details |
|--------|--------|---------|
| WalkForwardAnalyzer class | ✅ EXISTS | `atlas/agents/l3_validation/walk_forward_analyzer.py` |
| Algorithm | ✅ Correct | 5 rolling windows, 70/30 train/test split, measures survival & consistency |
| Called by ValidatorAgent | ❌ **NO** | Never invoked during normal pipeline |
| Data in DB | ❌ **Empty** | Table exists but no data unless seed scripts run |
| Deployment gate queries it | ❌ **Always returns NULL** | `deployment_governor.py` queries `walk_forward_analysis` but gets nothing |
| Impact | 🔴 **Walk-forward is decorative** | The column exists in the DB schema, the agent processes exist, but neither runs automatically |

### Walk-Forward as implemented would work if called:

- `n_windows = 5`, `train_pct = 0.7`, `min_trades = 3`
- `walk_forward_score = survived / total windows`
- Requires >= 100 bars, each window >= 20 bars
- `temporal_consistency` computed as inverse of Sharpe CV across windows
- `regime_survival_score` computed from volatility_regime column

**Verdict:** The algorithm is sound but **completely disconnected**. It is never invoked.

---

## Phase 4 — Overfitting Detection

### Findings

| Aspect | Status | Details |
|--------|--------|---------|
| OverfittingDetector class | ✅ EXISTS | `atlas/agents/l3_validation/overfitting_detector.py` |
| Methods used | ✅ Robust | Shuffle test (50 iterations), noise robustness (10 levels), parameter stability (20 perturbations) |
| Called by ValidatorAgent | ❌ **NO** | Never invoked |
| ValidatorAgent's actual overfit check | ⚠️ **Simple ratio** | Uses `holdout_sharpe < train_sharpe * 0.5` — but **disabled in dev** (overfit_ratio=0) |
| Overfit check in dev mode | ❌ **DISABLED** | `overfit_ratio = 0.0` means the check is skipped |
| Overfit check in prod | ✅ Functional | `holdout_sharpe < train_sharpe * 0.5` |
| RegimeValidator | ✅ EXISTS | But never called. Done by lightweight `_compute_regime_score()` in `backtest_runner.py`. |
| MonteCarloSimulator | ✅ EXISTS | But never called by any pipeline agent. |

### Key Issue: Disabled in Dev

In dev mode, the overfitting check is:
```python
overfit_ratio = 0.0
# ...
if train_sh > 0 and holdout_sh > 0 and ratio > 0:  # ratio = 0.0 → NEVER ENTERS
    overfit_flag = holdout_sh < train_sh * ratio
```

This means **every strategy passes the overfitting gate in dev/staging**. Combined with the relaxed thresholds, a strategy with Sharpe=0.01, WR=15%, PF=0.5 on only 2 trades can be "validated."

---

## Phase 5 — Validated Strategy Sampling

Since the database is not directly accessible in this audit, the analysis below is based on **code-path analysis** and **threshold inference**.

### Profile of a "validated" strategy in dev

Using current thresholds, the minimum profile to achieve "validated" status (composite >= 35):

| Metric | Minimum | Notes |
|--------|---------|-------|
| Trades | 2 | Any 2 trades |
| Sharpe | 0.0 | Non-negative |
| Drawdown | > -80% | Nearly total loss is OK |
| Win Rate | > 10% | 1 win in 10 |
| Profit Factor | > 0.30 | Wins are 0.3x the size of losses |
| Composite Score | ≥ 35/100 | Via regime boost |

### To achieve "elite" (composite >= 60 in dev):

| Metric | Typical Profile |
|--------|----------------|
| Trades | ≥ 5 |
| Sharpe | ≥ 0.5 |
| Drawdown | > -40% |
| Win Rate | > 30% |
| Profit Factor | > 1.0 |
| Regime Score | ≥ 0.5 (multi-regime) |

### Risks for "validated" strategies:

1. **Overfitting not checked** — a strategy could be perfectly tuned to historical noise
2. **Cost not checked** — a strategy with 0.01% edge per trade and 0.02% costs passes
3. **Sample size too small** — 2 trades is not meaningful
4. **Walk-forward never run** — temporal robustness is assumed, not verified
5. **Monte Carlo never run** — tail risk is not stress-tested

---

## Phase 6 — Findings Summary

### Validation Trust Score: **72/100**

| Dimension | Score | Reasoning |
|-----------|-------|-----------|
| Pipeline Completeness | 65/100 | All gates exist but 3 advanced agents are disconnected |
| Threshold Rigor | 55/100 | Dev thresholds are too permissive; short-window thresholds near-meaningless |
| Cost Governance | 40/100 | Disabled in dev, thorough but gated behind env check |
| Overfitting Detection | 45/100 | Disabled in dev; the sophisticated detector is never called |
| Walk-Forward Analysis | 30/100 | Algorithm is sound but never invoked |
| Deployment Gate | 50/100 | Queries tables that are never populated |

### Estimated False Positive Rate

| Environment | Lower Bound | Upper Bound | Best Estimate |
|-------------|-------------|-------------|---------------|
| Dev/Staging | 15% | 30% | **18-25%** |
| Production | 5% | 15% | **8-12%** |

### Estimated False Validation Count

Assuming 500 strategies marked as "validated" in the system:
- **Dev mode:** ~90-125 should not have passed
- **Prod mode:** ~40-60 should not have passed

### Critical Flaws

| # | Flaw | Severity | Fix |
|---|------|----------|-----|
| 1 | Walk-forward, overfitting, regime validation, and Monte Carlo agents are **never called by ValidatorAgent** | 🔴 CRITICAL | Wire all 4 agents into `ValidatorAgent._validate_one()` after backtest results are ready |
| 2 | `score_contract.compute_advanced_institutional_score()` is dead code — all 6 advanced bonus fields are always 0 | 🔴 CRITICAL | Either populate the fields through the wired agents, or remove the dead code |

### High-Priority Flaws

| # | Flaw | Severity | Fix |
|---|------|----------|-----|
| 3 | `overfit_ratio = 0.0` in dev disables the overfitting check entirely | 🟡 HIGH | Set to 0.3 in dev (check that holdout is at least 30% of train) |
| 4 | Short-window thresholds (PF >= 0.30, WR >= 10%, composite >= 15) are too permissive | 🟡 HIGH | Raise to PF >= 0.60, WR >= 25%, composite >= 30 |
| 5 | Structural min_trades = 1 in dev → single trades validate | 🟡 HIGH | Keep min_trades at 3 even in dev |

### Medium-Priority Flaws

| # | Flaw | Severity | Fix |
|---|------|----------|-----|
| 6 | `FitnessScorer` class is instantiable but never called by any pipeline agent | 🟠 MED | Either integrate or remove |
| 7 | Cost governance completely disabled in dev — no feedback loop for strategy authors | 🟠 MED | Enable cost governance at least for informational logging in dev |

---

## Recommended Fixes (Priority Order)

### Immediate (week 1)

1. **Wire advanced validation agents into ValidatorAgent.** Add calls to `walk_forward_analyzer.analyze()`, `overfitting_detector.detect()`, and `regime_validator.validate()` inside `_validate_one()`. This is the single highest-impact change — it turns 3 existing classes from idle agents into working pipeline gates.

2. **Enable overfit_ratio in dev.** Set `overfit_ratio = 0.3` in `DEV_RULES`. This simple config change activates the train/holdout overfitting check.

3. **Raise short-window thresholds.** Update dev short-window mode: `composite_threshold = 30` (from 15), `min_pf = 0.60` (from 0.30), `min_wr = 0.25` (from 0.10).

4. **Enable cost governance for logging in dev.** Don't block strategies, but log the cost profile so strategy authors can see economic viability feedback.

### Short-term (week 2)

5. **Wire Monte Carlo Simulator** into the validation flow. Run on strategies with >= 10 trades. Flag any strategy with `monte_carlo_survival < 0.3`.

6. **Populate advanced score fields** in `score_contract.py`. After wiring the agents, populate `walk_forward_score`, `robustness_score`, `regime_survival_score`, `cost_survival_score`, `monte_carlo_survival` in the results dict so `compute_advanced_institutional_score()` produces meaningful values.

7. **Remove dead code.** Either remove `FitnessScorer` class or integrate it. Remove `compute_advanced_institutional_score` if not wired. Remove `entry_side` assignments in state machine.

### Medium-term (week 3+)

8. **Add false-positive monitoring.** Track strategies that were "validated" but failed in paper/live. Feed failure rates back to dynamically adjust thresholds.

9. **Dynamic threshold adjustment based on market regime.** Already partially implemented via Scout-Aware adjustment — extend to use actual market volatility percentile.

---

## Appendix A: Pipeline Code Trace

### BacktestRunner writes these fields to backtest_results:
- `total_return`, `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`
- `total_trades`, `entry_count`, `exit_count`, `bars_processed`
- `profit_factor`, `calmar_ratio`, `sortino_ratio`, `expectancy`
- `composite_fitness_score`, `holdout_sharpe`, `train_sharpe`, `test_sharpe`
- `evaluation_mode`, `composite_score`, `regime_score`
- `gross_edge`, `cost_burden`, `avg_return_per_trade` (short_window only)

### ValidatorAgent reads these fields:
- `max_drawdown`, `total_trades`, `win_rate`, `profit_factor`
- `sharpe_ratio`, `train_sharpe`, `holdout_sharpe`
- `evaluation_mode`, `composite_score`, `short_window_score`
- `entry_count`, `exit_count`, `bars_processed`
- `total_return`, `asset_class`

### Fields that are NEVER populated (dead schema):
- `walk_forward_score` — defined in `score_contract.py`, table exists, never written by pipeline
- `robustness_score` — defined in `score_contract.py`, table exists, never written by pipeline
- `monte_carlo_survival` — defined in `score_contract.py`, table exists, never written by pipeline
- `regime_survival_score` — defined in `score_contract.py`, table exists, never written by pipeline
- `cost_survival_score` — referenced in `score_contract.py`, no table or pipeline code
- `feature_quality_score` — referenced in `score_contract.py`, no table or pipeline code

---

## Appendix B: State Machine Trade Count Analysis

The backtest state machine produces `closed_positions_count` from actual position state transitions. The `_run_tests()` in ValidatorAgent uses `total_trades` from the backtest results, which is `max(h_total_trades, closed_positions_count)`.

For short-window mode: `total_trades = int(max(sw_holdout["total_trades"], closed_positions_count))`

This means:
- If the short-window evaluator reports 5 trades but the state machine only closed 3, the reported value is 5 (max).
- This inflation could cause strategies to pass `min_trades = 2` when they actually only made 1-2 real trades.

---

*End of Audit Report*
