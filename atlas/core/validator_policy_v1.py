"""P6 T4 — validator_policy_v1: P3 status policy. PURE (no DB).

Faithful port of the FROZEN P3 decision pipeline (scratch/P3_VALIDATOR_DESIGN.md
+ scratch/p3_validator_sim.py :: classify). The validator is POLICY ENFORCEMENT:
it assigns lifecycle status; it does NOT recompute quality (P2 owns fitness) or
allocate capital (P4 owns that).

Pipeline (ordered gates — P3 design A2):
  0. STRUCTURAL SANITY  → fail            => failed_validation
  1. COVERAGE GATE      → missing any of {wf, mc, regime, overfit} => pending_validation
  2. SIGNIFICANCE FLOOR → n_trades < MIN_FLOOR caps below validated
  3. TIER ASSIGNMENT (consumes P2 deploy/research fitness):
       elite              := deploy ≥ ELITE_BAND   AND n ≥ PROD_FLOOR AND n ≥ MIN_FLOOR
       validated          := deploy ≥ DEPLOY_THRESH AND n ≥ MIN_FLOOR
       research_candidate := research ≥ RESEARCH_BAND
       failed_validation  := otherwise

FROZEN thresholds (do NOT change — handoff + P3 design Part C):
  DEPLOY_THRESH=35 (from P2) · MIN_FLOOR=50 · PROD_FLOOR=100 · ELITE_BAND=60 ·
  RESEARCH_BAND=30 · coverage = {walk_forward, monte_carlo, regime, overfit}
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from atlas.core.fitness_v1 import compute_fitness

# Frozen P3 thresholds
DEPLOY_THRESH: float = 35.0   # from P2 (frozen)
MIN_FLOOR: int = 50           # validated significance floor (calibration profile)
PROD_FLOOR: int = 100         # elite significance floor
ELITE_BAND: float = 60.0
RESEARCH_BAND: float = 30.0

# Status strings (existing taxonomy)
ELITE = "elite"
VALIDATED = "validated"
RESEARCH_CANDIDATE = "research_candidate"
PENDING_VALIDATION = "pending_validation"
FAILED_VALIDATION = "failed_validation"

COVERAGE_KEYS = ("walk_forward", "monte_carlo", "regime", "overfit")


def classify_status(
    deploy_fitness: float,
    research_fitness: float,
    n_trades: int,
    coverage_complete: bool,
    structural_ok: bool = True,
    *,
    deploy_thresh: float = DEPLOY_THRESH,
    min_floor: int = MIN_FLOOR,
    prod_floor: int = PROD_FLOOR,
    elite_band: float = ELITE_BAND,
    research_band: float = RESEARCH_BAND,
) -> str:
    """Pure tier logic — mirrors p3_validator_sim.classify with gate 0 (structural)
    prepended. Defaults are the frozen thresholds.
    """
    if not structural_ok:
        return FAILED_VALIDATION
    if not coverage_complete:
        return PENDING_VALIDATION
    sig_ok = n_trades >= min_floor
    if deploy_fitness >= elite_band and n_trades >= prod_floor and sig_ok:
        return ELITE
    if deploy_fitness >= deploy_thresh and sig_ok:
        return VALIDATED
    if research_fitness >= research_band:
        return RESEARCH_CANDIDATE
    return FAILED_VALIDATION


def coverage_complete(advanced: Mapping) -> bool:
    """Coverage gate: all four advanced validators present (non-None)."""
    return all(advanced.get(k) is not None for k in COVERAGE_KEYS)


def evaluate(
    trades: Sequence[Mapping],
    advanced: Mapping,
    structural_ok: bool = True,
    *,
    metrics: Optional[dict] = None,
) -> dict:
    """End-to-end: compute P2 fitness from trades + advanced scores, then classify.

    Args:
        trades: ledger trade list.
        advanced: mapping with keys walk_forward, monte_carlo, regime, overfit
            (any may be None → coverage incomplete).
        structural_ok: result of the upstream structural-sanity gate.
        metrics: optional precomputed ledger_metrics_v1.

    Returns:
        {status, deploy_fitness, research_fitness, n_trades, coverage_complete, fitness}
    """
    fit = compute_fitness(
        trades,
        walk_forward=advanced.get("walk_forward"),
        monte_carlo=advanced.get("monte_carlo"),
        regime=advanced.get("regime"),
        overfit=advanced.get("overfit"),
        metrics=metrics,
    )
    cov = coverage_complete(advanced)
    status = classify_status(
        deploy_fitness=fit["deploy_fitness"],
        research_fitness=fit["research_fitness"],
        n_trades=fit["n_trades"],
        coverage_complete=cov,
        structural_ok=structural_ok,
    )
    return dict(
        status=status,
        deploy_fitness=fit["deploy_fitness"],
        research_fitness=fit["research_fitness"],
        n_trades=fit["n_trades"],
        coverage_complete=cov,
        fitness=fit,
    )
