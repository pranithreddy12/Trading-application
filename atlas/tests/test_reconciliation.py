"""P6 T8 — hermetic unit tests for the reconciliation compute layer + service.

Pure functions over synthetic row dicts (no DB). Validates drift math, fitness
ranking, transition matrix, population summary, CSV/console builders, and that the
service is read-only (never calls a legacy write method).
"""
from decimal import Decimal

import pytest

from atlas.core import reconciliation as rc
from atlas.core.reconciliation import (
    ReconciliationService,
    build_console_report,
    build_csv_tables,
    compute_metric_drift,
    compute_population_summary,
    compute_transition_matrix,
    pct_delta,
    rank_by_fitness,
    summarize_distribution,
)


def _row(**kw):
    base = dict(
        strategy_id="s1", legacy_status="validated",
        legacy_sharpe=-68.0, legacy_win_rate=0.51, legacy_profit_factor="1.1",
        legacy_max_drawdown=-29.0,
        sharpe_v1=-10.0, win_rate_v1=0.46, profit_factor_v1=0.27, max_drawdown_v1=-0.29,
        n_trades_v1=759, deploy_fitness=0.0, research_fitness=17.5,
        status_v1="failed_validation", coverage_complete=False,
    )
    base.update(kw)
    return base


# ---- pure helpers ----

def test_pct_delta_guards_zero_and_none():
    assert pct_delta(None, 1.0) is None
    assert pct_delta(0.0, 1.0) is None
    assert pct_delta(-29.0, -0.29) == pytest.approx((-0.29 - -29.0) / 29.0 * 100)


def test_summarize_distribution():
    s = summarize_distribution([1.0, 2.0, 3.0, None])
    assert s["n"] == 3 and s["min"] == 1.0 and s["max"] == 3.0 and s["median"] == 2.0


# ---- metric drift ----

def test_metric_drift_abs_and_pct():
    rows = [_row()]
    out = compute_metric_drift(rows)
    by = {d["metric"]: d for d in out["per_strategy"]}
    # sharpe: shadow(-10) - legacy(-68) = +58
    assert by["sharpe"]["abs_delta"] == pytest.approx(58.0)
    # max_drawdown is the expected (percent→fraction) semantic change
    assert by["max_drawdown"]["expected_drift"] is True
    assert out["distribution"]["max_drawdown"]["expected_drift"] is True
    assert out["distribution"]["sharpe"]["abs"]["n"] == 1


def test_metric_drift_handles_decimal_and_text_pf():
    # legacy_profit_factor arrives as TEXT (from JSONB ->>) ; numerics as Decimal
    rows = [_row(legacy_sharpe=Decimal("-68"), legacy_profit_factor="1.1", profit_factor_v1=Decimal("0.27"))]
    out = compute_metric_drift(rows)
    by = {d["metric"]: d for d in out["per_strategy"]}
    assert by["profit_factor"]["legacy"] == pytest.approx(1.1)
    assert by["profit_factor"]["shadow"] == pytest.approx(0.27)
    assert by["profit_factor"]["abs_delta"] == pytest.approx(0.27 - 1.1)


# ---- fitness ranking ----

def test_rank_by_fitness_orders_desc():
    rows = [
        _row(strategy_id="a", deploy_fitness=0.0, research_fitness=10.0),
        _row(strategy_id="b", deploy_fitness=42.0, research_fitness=79.0),
        _row(strategy_id="c", deploy_fitness=0.0, research_fitness=25.0),
    ]
    ranked = rank_by_fitness(rows)
    assert [e["strategy_id"] for e in ranked] == ["b", "c", "a"]
    assert ranked[0]["rank"] == 1 and ranked[-1]["rank"] == 3


# ---- transition matrix ----

def test_transition_matrix_counts():
    rows = [
        _row(strategy_id="a", legacy_status="validated", status_v1="failed_validation"),
        _row(strategy_id="b", legacy_status="validated", status_v1="pending_validation"),
        _row(strategy_id="c", legacy_status="validated", status_v1="failed_validation"),
        _row(strategy_id="d", legacy_status="elite", status_v1="pending_validation"),
    ]
    tm = compute_transition_matrix(rows)
    assert tm["matrix"]["validated"]["failed_validation"] == 2
    assert tm["matrix"]["validated"]["pending_validation"] == 1
    assert tm["matrix"]["elite"]["pending_validation"] == 1
    # transitions list sorted by count desc
    assert tm["transitions"][0]["count"] == 2


# ---- population summary ----

def test_population_summary_counts_and_coverage():
    rows = [
        _row(status_v1="failed_validation", coverage_complete=False),
        _row(status_v1="pending_validation", coverage_complete=False),
        _row(status_v1="validated", coverage_complete=True),
    ]
    legacy_counts = {"validated": 222, "failed_validation": 400}
    ps = compute_population_summary(rows, legacy_counts)
    assert ps["reconciled_strategies"] == 3
    assert ps["legacy_status_counts"]["validated"] == 222
    assert ps["shadow_status_counts"]["validated"] == 1
    assert ps["coverage"] == {"present": 1, "missing": 2}


# ---- builders ----

def test_build_csv_tables_shapes():
    report = {
        "row_count": 1,
        "metric_drift": compute_metric_drift([_row()]),
        "fitness_ranking": rank_by_fitness([_row()]),
        "validator_transitions": compute_transition_matrix([_row()]),
        "population_summary": compute_population_summary([_row()], {"validated": 1}),
    }
    tables = build_csv_tables(report)
    for fname in ("metric_drift.csv", "metric_drift_distribution.csv", "fitness_ranking.csv",
                  "validator_transitions.csv", "population_summary.csv"):
        assert fname in tables
        header, data_rows = tables[fname]
        assert isinstance(header, list) and isinstance(data_rows, list)
    # console report renders without error and mentions the sections
    text = build_console_report(report)
    assert "METRIC DRIFT" in text and "TRANSITION MATRIX" in text and "POPULATION SUMMARY" in text


# ---- service is read-only ----

class _ROFake:
    """Fake db exposing only the read methods; any legacy write attr is recorded."""
    def __init__(self, rows, legacy_counts):
        self._rows = rows
        self._legacy = legacy_counts
        self.writes = []

    async def get_reconciliation_rows(self):
        return self._rows

    async def get_legacy_status_counts(self):
        return self._legacy

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
async def test_service_generate_is_read_only():
    db = _ROFake([_row(), _row(strategy_id="s2", status_v1="pending_validation")], {"validated": 222})
    report = await ReconciliationService(db).generate()
    assert report["row_count"] == 2
    assert "metric_drift" in report and "fitness_ranking" in report
    assert "validator_transitions" in report and "population_summary" in report
    assert db.writes == []  # no legacy/v1 write method was ever called
