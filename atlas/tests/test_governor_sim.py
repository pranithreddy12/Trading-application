"""P6 T10 — hermetic unit tests for the shadow governor simulation.

Pure functions over synthetic rows (no DB). Validates frozen P4 eligibility +
defensive gate, selection, allocation caps, defense-in-depth, and that the
service is read-only.
"""
import pytest

from atlas.core import governor_sim as gov
from atlas.core.governor_sim import (
    GovernorSimulator,
    evaluate_eligibility,
    force_stale_status,
    simulate_allocation,
    simulate_governor,
    simulate_promotion,
)


def _ok(**kw):
    base = dict(strategy_id="g", status_v1="validated", n_trades=150,
                coverage_complete=True, overfit=0.1, deploy_fitness=60.0, family="f")
    base.update(kw)
    return base


# ---- eligibility gates (first failing gate wins) ----

def test_eligible_when_all_gates_pass():
    ok, reason = evaluate_eligibility(_ok())
    assert ok is True and reason is None


def test_not_certified_rejected():
    ok, reason = evaluate_eligibility(_ok(status_v1="research_candidate"))
    assert ok is False and reason == "not_certified"


def test_underpowered_rejected():
    ok, reason = evaluate_eligibility(_ok(n_trades=1))
    assert ok is False and reason == "underpowered"


def test_coverage_incomplete_rejected():
    ok, reason = evaluate_eligibility(_ok(coverage_complete=False))
    assert ok is False and reason == "coverage_incomplete"


def test_overfit_rejected():
    ok, reason = evaluate_eligibility(_ok(overfit=1.0))
    assert ok is False and reason == "overfit"


def test_deploy_below_threshold_rejected():
    ok, reason = evaluate_eligibility(_ok(deploy_fitness=10.0))
    assert ok is False and reason == "deploy_below_threshold"


def test_overfit_absent_is_enforced_via_deploy():
    # real rows have no overfit; a strong deploy still passes (overfit subsumed)
    ok, reason = evaluate_eligibility(_ok(overfit=None, deploy_fitness=60.0))
    assert ok is True
    # and a zero deploy (what overfit>=0.5 would have produced) is caught
    ok2, reason2 = evaluate_eligibility(_ok(overfit=None, deploy_fitness=0.0))
    assert ok2 is False and reason2 == "deploy_below_threshold"


# ---- selection ----

def test_promotion_ranks_and_caps_concurrency():
    rows = [_ok(strategy_id=f"s{i}", deploy_fitness=float(i)) for i in range(15)]
    sel = simulate_promotion(rows, max_concurrent=10)
    assert len(sel) == 10
    assert sel[0]["deploy_fitness"] == 14.0  # highest first
    assert sel[-1]["deploy_fitness"] == 5.0


# ---- allocation caps ----

def test_allocation_respects_family_cap():
    # 4 mean_reversion eligible -> family cap 40% of 50k = 20k must bind
    pool = [_ok(strategy_id=f"mr{i}", family="mean_reversion", deploy_fitness=60.0) for i in range(4)]
    out = simulate_allocation(pool, budget=50_000)
    assert out["family_totals"]["mean_reversion"] <= out["family_cap_amt"] + 1e-6
    assert out["family_totals"]["mean_reversion"] == pytest.approx(20_000.0, abs=1.0)


def test_allocation_respects_per_strategy_cap():
    # one dominant strategy cannot exceed 20% of budget
    pool = [_ok(strategy_id="big", deploy_fitness=1000.0, family="a"),
            _ok(strategy_id="small", deploy_fitness=1.0, family="b")]
    out = simulate_allocation(pool, budget=50_000)
    big = next(a for a in out["allocations"] if a["strategy_id"] == "big")
    assert big["capital"] <= out["per_strategy_cap_amt"] + 1e-6  # <= 10k


# ---- full pass + defense in depth ----

def test_simulate_governor_zero_eligible_on_uncertified_population():
    rows = [_ok(status_v1="pending_validation"), _ok(status_v1="failed_validation"),
            _ok(status_v1="research_candidate")]
    res = simulate_governor(rows)
    assert res["eligible_count"] == 0 and res["promoted_count"] == 0
    assert res["allocated_capital"] == 0.0
    assert res["rejection_breakdown"]["not_certified"] == 3


def test_defense_in_depth_rejects_forced_stale_status():
    # underpowered / overfit / uncovered / low-deploy, but stale status forced valid
    junk = [
        _ok(strategy_id="n1", status_v1="x", n_trades=1),
        _ok(strategy_id="of", status_v1="x", overfit=1.0),
        _ok(strategy_id="cov", status_v1="x", coverage_complete=False),
        _ok(strategy_id="dep", status_v1="x", deploy_fitness=5.0),
    ]
    forced = force_stale_status(junk, "validated")
    res = simulate_governor(forced)
    assert res["eligible_count"] == 0
    rb = res["rejection_breakdown"]
    assert rb["underpowered"] == 1 and rb["overfit"] == 1
    assert rb["coverage_incomplete"] == 1 and rb["deploy_below_threshold"] == 1


def test_genuine_good_promoted_and_allocated():
    pool = [_ok(strategy_id=f"mr{i}", family="mean_reversion", deploy_fitness=60.0 - i) for i in range(4)]
    pool += [_ok(strategy_id=f"mo{i}", family="momentum", deploy_fitness=65.0 - i) for i in range(2)]
    res = simulate_governor(pool, budget=50_000)
    assert res["eligible_count"] == 6 and res["promoted_count"] == 6
    assert res["allocated_capital"] > 0
    assert res["allocation"]["family_totals"]["mean_reversion"] == pytest.approx(20_000.0, abs=1.0)


# ---- service is read-only ----

class _ROFake:
    def __init__(self, rows):
        self._rows = rows
        self.writes = []

    async def get_shadow_governor_rows(self):
        return self._rows

    def __getattr__(self, name):
        if name.startswith(("save_", "update_", "write_", "ensure_")):
            def _rec(*a, **k):
                self.writes.append(name)
                async def _n():
                    return None
                return _n()
            return _rec
        raise AttributeError(name)


@pytest.mark.asyncio
async def test_service_run_is_read_only():
    db = _ROFake([_ok(status_v1="pending_validation"), _ok(status_v1="failed_validation")])
    res = await GovernorSimulator(db).run()
    assert res["eligible_count"] == 0
    assert db.writes == []


@pytest.mark.asyncio
async def test_service_defense_in_depth_forces_status():
    db = _ROFake([_ok(strategy_id="u", status_v1="failed_validation", n_trades=1)])
    res = await GovernorSimulator(db).run_defense_in_depth()
    # forced to 'validated' but n_trades=1 -> still rejected underpowered
    assert res["eligible_count"] == 0
    assert res["rejection_breakdown"]["underpowered"] == 1
    assert db.writes == []
