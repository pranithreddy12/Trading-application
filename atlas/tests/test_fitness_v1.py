"""P6 T5 — unit tests for atlas/core/fitness_v1 (T3).

Proves: (a) the frozen P2 gate behavior (1-trade -> 0, junk -> 0, genuine-good
-> deploy ≥ 35), (b) equivalence to the frozen calibration reference
scratch/p2_calibration_sweep.py at the locked operating point (cost^0.75, op_tol 0.5).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from atlas.core.fitness_v1 import compute_fitness

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


# The FROZEN genuine-good control (P2 Part C / p2_calibration_sweep): 120 trades,
# wf=0.6 mc=0.7 regime=0.5 overfit=0.1 -> deploy ≈ 42.5 at the locked point.
GENUINE_GOOD = _mk([0.008 + 0.004 * ((i % 5) / 4) for i in range(120)])
GOOD_ADV = dict(walk_forward=0.6, monte_carlo=0.7, regime=0.5, overfit=0.1)


def test_one_trade_scores_zero():
    f = compute_fitness(_mk([0.05]), walk_forward=None, monte_carlo=None, regime=None, overfit=None)
    assert f["deploy_fitness"] == 0.0
    assert f["insufficient"] is True


def test_below_hard_floor_scores_zero():
    # < N_HARD (10) trades -> n_gate 0 -> deploy 0 even with great pnls
    f = compute_fitness(_mk([0.02, 0.03, 0.02]), walk_forward=0.6, monte_carlo=0.7, regime=0.5, overfit=0.1)
    assert f["deploy_fitness"] == 0.0


def test_genuine_good_deploy_above_threshold():
    f = compute_fitness(GENUINE_GOOD, **GOOD_ADV)
    assert f["deploy_fitness"] > 35.0
    assert f["deploy_fitness"] == pytest.approx(42.5, abs=0.5)   # frozen sim value
    assert f["research_fitness"] > f["deploy_fitness"]            # research = 100·Q (ungated)


def test_significance_ramp_suppresses_50_trade_winner():
    """FROZEN-MATH NOTE: the same excellent shape at 50 trades scores < 35, because
    the P2 n_gate ramps 10->100. Only a ~100+-trade winner clears 35 (see genuine-good).
    This documents the intended significance down-weight, not a defect."""
    f50 = compute_fitness(_mk([0.008 + 0.004 * ((i % 5) / 4) for i in range(50)]), **GOOD_ADV)
    assert f50["deploy_fitness"] < 35.0
    assert f50["deploy_fitness"] == pytest.approx(19.1, abs=1.0)


@pytest.mark.parametrize(
    "name,pnls,adv",
    [
        ("3-lucky", [0.02, 0.03, 0.02], dict(walk_forward=None, monte_carlo=None, regime=None, overfit=0.1)),
        ("churn-trap", [0.001] * 200, dict(walk_forward=0.3, monte_carlo=0.4, regime=0.3, overfit=0.2)),
        ("overfit", [0.012] * 120, dict(walk_forward=0.6, monte_carlo=0.7, regime=0.5, overfit=1.0)),
    ],
)
def test_junk_scores_zero(name, pnls, adv):
    f = compute_fitness(_mk(pnls), **adv)
    assert f["deploy_fitness"] == 0.0, name


def test_matches_frozen_calibration_reference():
    """deploy_fitness equals scratch/p2_calibration_sweep.fitness at the locked
    operating point (cost_exp=0.75, op_tol=0.5)."""
    pytest.importorskip("asyncpg")
    if _SCRATCH not in sys.path:
        sys.path.insert(0, _SCRATCH)
    import p2_calibration_sweep as ref  # frozen calibration sweep

    cases = [
        (GENUINE_GOOD, 0.6, 0.7, 0.5, 0.1),
        (_mk([0.012] * 120), 0.6, 0.7, 0.5, 1.0),    # overfit junk
        (_mk([0.001] * 200), 0.3, 0.4, 0.3, 0.2),    # churn trap
        (_mk([0.02, 0.03, 0.02]), None, None, None, 0.1),  # lucky few
    ]
    for trades, wf, mc, rg, ov in cases:
        mine = compute_fitness(trades, walk_forward=wf, monte_carlo=mc, regime=rg, overfit=ov)
        theirs = ref.fitness(trades, wf, mc, rg, ov, cost_exp=0.75, op_tol=0.5)
        assert mine["deploy_fitness"] == pytest.approx(theirs, rel=1e-9, abs=1e-9)
