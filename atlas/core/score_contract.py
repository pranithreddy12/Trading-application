"""
score_contract.py — Single Source of Truth for Institutional Strategy Scoring.

This contract normalizes scoring logic across the entire ATLAS ecosystem (Validators, Mutators, Ideators, Meta-Agents).
It resolves schema drift by strictly mapping physical backtest result fields to a unified 'institutional_score'.

Phase 11 Extension — Advanced Validation & Pattern Intelligence Scoring:
NOTE: These fields are NOW populated by BacktestRunner._run_advanced_validation()
      after each backtest completes (wired June 2026).

New weighted score inputs (optional, additive):
- walk_forward_score      — temporal robustness from Walk-Forward Analyzer (NOW WIRED)
- monte_carlo_survival    — survival rate from Monte Carlo Simulator (NOW WIRED)
- robustness_score        — overfitting resistance from Overfitting Detector (NOW WIRED)
- regime_survival_score   — regime count from Regime Validator (NOW WIRED)
- cost_survival_score     — cost stress survival from Cost Stress Tester (not yet wired)
- feature_quality_score   — feature ranking quality from Feature Importance Engine (not yet wired)

Final scoring formula:
  composite = base_score × regime_adjustment
            + walk_forward_bonus
            + monte_carlo_bonus
            + robustness_bonus
            + regime_survival_bonus
            + cost_survival_bonus
            + feature_quality_bonus
  clamped to [0, 100]
"""

PRIMARY_SCORE_FIELD = "institutional_score"

# Phase 11 — Advanced validation weights (each contributes up to its max_bonus)
ADVANCED_WEIGHTS = {
    "walk_forward_score": {"weight": 0.15, "max_bonus": 15.0},
    "monte_carlo_survival": {"weight": 0.12, "max_bonus": 12.0},
    "robustness_score": {"weight": 0.10, "max_bonus": 10.0},
    "regime_survival_score": {"weight": 0.10, "max_bonus": 10.0},
    "cost_survival_score": {"weight": 0.08, "max_bonus": 8.0},
    "feature_quality_score": {"weight": 0.05, "max_bonus": 5.0},
}


def compute_regime_adjustment(results: dict) -> float:
    """
    Compute a regime-based score adjustment [0.0, 0.3].

    reward_scheme:
      - regime_score >= 0.5 (multi-regime): multi_regime_bonus = +0.2
      - regime_score < 0.5 (single-regime): no bonus, slight penalty = -0.05
      - No data: neutral adjustment = 0.0
    """
    regime_score = float(results.get("regime_score", 0.0))
    if regime_score >= 0.5:
        return 0.2  # bonus for multi-regime robustness
    elif regime_score > 0.0:
        return -0.05  # slight penalty for single-regime overfit
    return 0.0  # no data adjustment


def compute_institutional_score(results: dict) -> float:
    """
    Computes the canonical institutional score for a strategy based on its backtest results.

    Scoring formula:
      1. Base score = max(composite_score, short_window_score, 0)
      2. Regime adjustment = compute_regime_adjustment(results)
      3. Final = clamp(base_score * (1.0 + regime_adjustment), 0, 100)

    This ensures:
      - Multi-regime strategies get a boost (reward robustness)
      - Single-regime strategies are slightly penalized (overfit risk)
      - Regime_score of 0 (no trades) has no effect
    """
    if not results:
        return 0.0

    # HARD SANITY GATE: Insufficient trades = zero score
    total_trades = int(results.get("total_trades", 0) or 0)
    if total_trades < 20:
        return 0.0  # Inadequate sample size for statistical significance

    # HARD SANITY GATE: Invalid or missing Sharpe = zero score
    sharpe = results.get("sharpe_ratio", results.get("sharpe", results.get("holdout_sharpe", 0.0)))
    if sharpe is None or sharpe == 0.0 or (isinstance(sharpe, float) and (sharpe != sharpe)):
        return 0.0
    
    # HARD SANITY GATE: Missing profit_factor or expectancy = zero score
    pf = results.get("profit_factor")
    if pf is None or (isinstance(pf, float) and (pf != pf)):
        return 0.0
    expectancy = results.get("expectancy")
    if expectancy is None or (isinstance(expectancy, float) and (expectancy != expectancy)):
        return 0.0

    # If the system has migrated to explicitly passing 'institutional_score'
    if "institutional_score" in results:
        return float(results["institutional_score"])

    # Determine base score
    base_score = 0.0
    if "composite_score" in results:
        base_score = float(results["composite_score"])
    elif "short_window_score" in results:
        base_score = float(results["short_window_score"])

    base_score = max(base_score, 0.0)

    # Apply regime adjustment
    adjustment = compute_regime_adjustment(results)
    adjusted = base_score * (1.0 + adjustment)

    # Clamp to [0, 100]
    return max(0.0, min(100.0, adjusted))


def compute_advanced_institutional_score(results: dict) -> float:
    """
    Phase 11 — Advanced institutional score incorporating walk-forward, Monte Carlo,
    overfit detection, regime validation, cost stress, and feature importance.

    Formula:
      composite = base_score × regime_adjustment
                + ∑(advanced_score × weight × scale_factor)

    where each advanced_score is normalized [0, 1] and multiplied by its max_bonus.
    """
    if not results:
        return 0.0

    base_score = 0.0
    if "composite_score" in results:
        base_score = float(results["composite_score"])
    elif "short_window_score" in results:
        base_score = float(results["short_window_score"])
    base_score = max(base_score, 0.0)

    # Regime adjustment on base
    adjustment = compute_regime_adjustment(results)
    composite = base_score * (1.0 + adjustment)

    # Add advanced validation bonuses
    for field, cfg in ADVANCED_WEIGHTS.items():
        raw = results.get(field)
        if raw is not None:
            try:
                val = float(raw)
                # Normalize: most are [0, 1] but clamp to be safe
                normalized = max(0.0, min(1.0, val))
                composite += normalized * cfg["max_bonus"]
            except (ValueError, TypeError):
                pass

    return max(0.0, min(100.0, composite))


# =====================================================================
# Sprint 1B — ADVANCED VALIDATOR GOVERNANCE (additive hard-gate overlay)
# =====================================================================
# This is a SEPARATE pass/fail overlay on the four advanced validators. It does
# NOT modify compute_institutional_score (the base score is preserved). The
# caller (ValidatorAgent) decides whether to ENFORCE (block validated/elite) or
# run ADVISORY (compute + log only).
#
# CRITICAL UNIT NOTE: all four metrics are FRACTIONS in [0, 1] as persisted by
# BacktestRunner._run_advanced_validation (walk_forward_score, monte_carlo_
# survival_score, overfit_probability, regime_survival_score). The regime gate
# uses the integer COUNT n_regimes_survived (0..5) to map directly to the master
# spec's "≥3 of 5 regimes". Thresholds must therefore be expressed on these
# native scales — NOT 0..100 (the bug that made DeploymentGovernor's
# min_walk_forward_score of 30/40/50 unreachable).
ADVANCED_GOVERNANCE_THRESHOLDS = {
    # Calibration: lets the current best strategies through while backtests are
    # still short. Empirically (June 2026): wf max 0.80/avg 0.09, mc avg 0.39,
    # overfit avg 0.18, n_regimes_survived max 3.
    "calibration": {
        "min_walk_forward_score": 0.30,
        "min_monte_carlo_survival": 0.50,
        "max_overfit_probability": 0.50,
        "min_regimes_survived": 2,
    },
    # Spec: master-spec Section VII targets (paper minimums). Almost nothing
    # passes today — intended for once backtests produce ≥100 trades / longer
    # windows. Same precedence as the Sprint 1 trade-count floor.
    "spec": {
        "min_walk_forward_score": 0.60,   # spec: profitable in >=60% of windows
        "min_monte_carlo_survival": 0.70,
        "max_overfit_probability": 0.50,
        "min_regimes_survived": 3,         # spec: >=3 of 5 regimes
    },
}


def evaluate_advanced_governance(advanced: dict, profile: str = "calibration") -> dict:
    """Additive hard-gate evaluation over the four advanced validators.

    Policy = REQUIRE-COVERAGE: a missing metric (no validator row) is a FAILURE —
    a strategy cannot be considered robust without having survived the adversary
    layer. The caller enforces or merely logs this result.

    Args:
        advanced: dict from TimescaleClient.get_advanced_validation(); keys
            walk_forward_score, monte_carlo_survival_score, overfit_probability,
            regime_survival_score, n_regimes_survived (any may be None).
        profile: "calibration" (default) or "spec".

    Returns:
        {passed: bool, failures: [str], profile: str, thresholds: {...},
         details: {metric: value_or_None}}
    """
    th = ADVANCED_GOVERNANCE_THRESHOLDS.get(
        profile, ADVANCED_GOVERNANCE_THRESHOLDS["calibration"]
    )
    advanced = advanced or {}
    failures: list[str] = []

    def _num(key):
        v = advanced.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    wf = _num("walk_forward_score")
    mc = _num("monte_carlo_survival_score")
    of = _num("overfit_probability")
    nreg = _num("n_regimes_survived")

    # walk-forward (higher better)
    if wf is None:
        failures.append("missing:walk_forward_score")
    elif wf < th["min_walk_forward_score"]:
        failures.append(f"walk_forward {wf:.3f} < {th['min_walk_forward_score']}")

    # monte-carlo survival (higher better)
    if mc is None:
        failures.append("missing:monte_carlo_survival")
    elif mc < th["min_monte_carlo_survival"]:
        failures.append(f"monte_carlo {mc:.3f} < {th['min_monte_carlo_survival']}")

    # overfit probability (LOWER better)
    if of is None:
        failures.append("missing:overfit_probability")
    elif of > th["max_overfit_probability"]:
        failures.append(f"overfit {of:.3f} > {th['max_overfit_probability']}")

    # regime survival count (higher better)
    if nreg is None:
        failures.append("missing:n_regimes_survived")
    elif nreg < th["min_regimes_survived"]:
        failures.append(f"regimes_survived {nreg:.0f} < {th['min_regimes_survived']}")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "profile": profile,
        "thresholds": dict(th),
        "details": {
            "walk_forward_score": wf,
            "monte_carlo_survival_score": mc,
            "overfit_probability": of,
            "n_regimes_survived": nreg,
        },
    }
