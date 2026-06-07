"""P6 T5 — unit tests for atlas/core/validator_policy_v1 (T4).

Proves: (a) the frozen P3 tier logic for each gate, (b) end-to-end status on the
genuine-good control, (c) equivalence to scratch/p3_validator_sim.classify.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from atlas.core import validator_policy_v1 as vp
from atlas.core.validator_policy_v1 import classify_status, evaluate

_SCRATCH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scratch"))


def _mk(pnls, days=30):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i, p in enumerate(pnls):
        t0 = base + timedelta(days=days * i / max(len(pnls), 1))
        out.append(
            dict(pnl_pct=p, bars_held=10, entry_time=t0, exit_time=t0 + timedelta(minutes=10))
        )
    return out


GENUINE_GOOD = _mk([0.008 + 0.004 * ((i % 5) / 4) for i in range(120)])
FULL_COVERAGE = dict(walk_forward=0.6, monte_carlo=0.7, regime=0.5, overfit=0.1)


# ---- frozen tier logic (gate by gate) ----

def test_structural_fail_is_failed_validation():
    assert classify_status(99, 99, 200, True, structural_ok=False) == vp.FAILED_VALIDATION


def test_missing_coverage_is_pending():
    assert classify_status(99, 99, 200, coverage_complete=False) == vp.PENDING_VALIDATION


def test_elite_requires_band_and_prod_floor():
    assert classify_status(70, 80, 120, True) == vp.ELITE          # deploy>=60, n>=100
    # deploy high enough for elite band but below PROD_FLOOR(100) -> validated, not elite
    assert classify_status(70, 80, 80, True) == vp.VALIDATED


def test_validated_requires_deploy_thresh_and_min_floor():
    assert classify_status(40, 60, 80, True) == vp.VALIDATED       # deploy>=35, n>=50
    # significance floor cliff: deploy high but n < MIN_FLOOR(50) cannot validate
    assert classify_status(70, 50, 30, True) == vp.RESEARCH_CANDIDATE


def test_research_then_failed():
    assert classify_status(10, 30, 120, True) == vp.RESEARCH_CANDIDATE  # research>=30
    assert classify_status(10, 20, 120, True) == vp.FAILED_VALIDATION   # below research band


# ---- end-to-end ----

def test_genuine_good_validates_with_full_coverage():
    r = evaluate(GENUINE_GOOD, FULL_COVERAGE)
    assert r["status"] == vp.VALIDATED
    assert r["deploy_fitness"] > 35.0
    assert r["coverage_complete"] is True


def test_genuine_good_missing_validator_is_pending():
    adv = dict(FULL_COVERAGE)
    adv["monte_carlo"] = None
    r = evaluate(GENUINE_GOOD, adv)
    assert r["status"] == vp.PENDING_VALIDATION


def test_underpowered_high_fitness_cannot_validate():
    # 50-trade winner: deploy ≈ 19 < 35 AND n < MIN_FLOOR -> not validated
    r = evaluate(_mk([0.008 + 0.004 * ((i % 5) / 4) for i in range(50)]), FULL_COVERAGE)
    assert r["status"] != vp.VALIDATED
    assert r["status"] != vp.ELITE


# ---- equivalence to the frozen reference ----

def test_matches_frozen_p3_classify():
    pytest.importorskip("asyncpg")
    if _SCRATCH not in sys.path:
        sys.path.insert(0, _SCRATCH)
    import p3_validator_sim as ref

    grid = [
        (70, 80, 120, True), (70, 80, 80, True), (40, 60, 80, True),
        (70, 50, 30, True), (10, 30, 120, True), (10, 20, 120, True),
        (60, 70, 100, True), (34.9, 50, 200, True), (35.0, 0, 50, True),
    ]
    for deploy, research, n, cov in grid:
        f = {"deploy": deploy, "research": research, "n": n}
        theirs = ref.classify(
            f, cov, vp.MIN_FLOOR, vp.PROD_FLOOR, vp.ELITE_BAND, vp.RESEARCH_BAND
        )
        mine = classify_status(deploy, research, n, cov)
        assert mine == theirs, (deploy, research, n, cov, mine, theirs)
