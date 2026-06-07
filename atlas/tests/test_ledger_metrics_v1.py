"""P6 T5 — unit tests for atlas/core/ledger_metrics_v1 (T2).

Proves: (a) domain invariants from the frozen P1 spec, (b) byte-for-byte
equivalence to the frozen reference scratch/ledger_metrics.py.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

from atlas.core.ledger_metrics_v1 import compute_ledger_metrics

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


def test_empty_returns_zero_trades():
    assert compute_ledger_metrics([]) == {"n_trades": 0}


def test_domains_on_mixed_set():
    m = compute_ledger_metrics(_mk([0.05, -0.06, 0.03, -0.08, 0.02, -0.01, 0.04, -0.03]))
    assert m["n_trades"] == 8
    assert -1.0 <= m["max_drawdown"] <= 0.0           # fraction, never positive, >= -1
    assert -10.0 <= m["sharpe"] <= 10.0               # clamped
    assert -10.0 <= m["sortino"] <= 10.0
    assert 0.0 <= m["win_rate"] <= 1.0
    assert m["profit_factor"] <= 5.0                   # capped


def test_extreme_drawdown_clipped_to_minus_one():
    # catastrophic losses -> equity floored, drawdown clipped at -1
    m = compute_ledger_metrics(_mk([-9.0, -9.0, -9.0]))
    assert m["max_drawdown"] >= -1.0
    assert m["max_drawdown"] <= 0.0


def test_all_winners_pf_capped_and_zero_drawdown():
    m = compute_ledger_metrics(_mk([0.01, 0.012, 0.011, 0.013]))
    assert m["win_rate"] == 1.0
    assert m["profit_factor"] == 5.0          # no losses -> capped at 5.0
    assert m["max_drawdown"] == 0.0            # monotone-increasing equity


def test_avg_duration_from_ledger_not_hardcoded():
    trades = _mk([0.01, -0.01, 0.02])
    for t in trades:
        t["bars_held"] = 42
    assert compute_ledger_metrics(trades)["avg_trade_duration_bars"] == 42


@pytest.mark.parametrize(
    "pnls",
    [
        [0.05, -0.06, 0.03, -0.08, 0.02, -0.01, 0.04, -0.03],
        [0.008 + 0.004 * ((i % 5) / 4) for i in range(120)],
        [0.02, 0.03, 0.02],
        [0.001] * 200,
        [-0.5, 0.4, -0.3, 0.2],
    ],
)
def test_matches_frozen_scratch_reference(pnls):
    """Byte-for-byte equality with scratch/ledger_metrics.py (the frozen reference)."""
    pytest.importorskip("asyncpg")  # scratch module imports asyncpg at import time
    if _SCRATCH not in sys.path:
        sys.path.insert(0, _SCRATCH)
    import ledger_metrics as ref  # scratch/ledger_metrics.py

    trades = _mk(pnls)
    mine = compute_ledger_metrics(trades)
    theirs = ref.compute_ledger_metrics(trades)
    assert mine.keys() == theirs.keys()
    for k in mine:
        assert mine[k] == pytest.approx(theirs[k], rel=1e-12, abs=1e-12), k
