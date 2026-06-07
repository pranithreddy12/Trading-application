"""P6 T2 — ledger_metrics_v1: canonical single-source metric derivation from the
trade ledger. PURE (no DB). Byte-for-byte port of the FROZEN reference
scratch/ledger_metrics.py :: compute_ledger_metrics (P1 spec
scratch/LEDGER_METRICS_V1_SPEC.md).

Frozen conventions (immutable — see spec):
  ROUNDTRIP cost = 0.004 (applied once per trade, price-fraction units)
  position size  = 0.10 of equity per trade
  units          = FRACTIONS throughout (NO ×100 anywhere)
  per-trade net  = (pnl_pct - 0.004) * 0.10
  equity         = trade-sequenced cumprod(1 + r_i) (entry-time order)
  max_drawdown   = min(equity/cummax - 1), clipped [-1, 0]  (fraction)
  win/PF/expect  = per-trade; PF capped 5.0
  sharpe/sortino = per-trade (mean/std)·√(trades_per_year), clamped [-10, 10]
  trades_per_year= N·365/span_days; span_days = (last exit - first entry) floor 0.5

This module ONLY computes; it never reads or writes the database. Callers supply
the trade list (e.g. backtest_runner from its in-memory trades, or the backfill
script from backtest_trades).
"""
from __future__ import annotations

import math
import statistics as st
from typing import Mapping, Sequence

# Frozen constants (P1 spec — do not change)
ROUNDTRIP: float = 0.004
SIZE: float = 0.10
PF_CAP: float = 5.0
SHARPE_CLAMP: float = 10.0


def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_ledger_metrics(trades: Sequence[Mapping]) -> dict:
    """Compute the canonical metric set from a trade ledger.

    Args:
        trades: sequence of mappings each with keys
            pnl_pct (float), bars_held (int|float), entry_time, exit_time
            (entry_time/exit_time must support subtraction → timedelta, i.e.
            datetime objects). Order need not be pre-sorted; sorted internally
            by entry_time.

    Returns:
        dict of metrics (all fractions). For N == 0 returns {"n_trades": 0}.
    """
    N = len(trades)
    if N == 0:
        return {"n_trades": 0}

    tr = sorted(trades, key=lambda t: t["entry_time"])

    # per-trade net & gross scaled returns
    r = [(float(t["pnl_pct"]) - ROUNDTRIP) * SIZE for t in tr]
    g = [float(t["pnl_pct"]) * SIZE for t in tr]

    # net equity curve (trade-sequenced)
    eq, e = [], 1.0
    for x in r:
        e *= (1.0 + x)
        eq.append(e)
    total_return = eq[-1] - 1.0

    # gross equity (for cost burden / retention)
    ge = 1.0
    for x in g:
        ge *= (1.0 + x)
    gross_edge = ge - 1.0
    cost_burden = gross_edge - total_return

    # drawdown (fraction, clipped >= -1)
    peak, mdd = -1e9, 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    mdd = clip(mdd, -1.0, 0.0)

    # per-trade win / PF / expectancy (NET)
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x < 0]
    win_rate = len(wins) / N
    pf = (sum(wins) / abs(sum(losses))) if losses else (PF_CAP if wins else 0.0)
    pf = min(pf, PF_CAP)
    expectancy = sum(r) / N

    # annualization from trade-time span
    span_days = max(
        (tr[-1]["exit_time"] - tr[0]["entry_time"]).total_seconds() / 86400.0, 0.5
    )
    tpy = N * 365.0 / span_days
    mu = st.mean(r)
    sd = st.pstdev(r) if N > 1 else 0.0
    sharpe = (
        clip((mu / sd) * math.sqrt(tpy), -SHARPE_CLAMP, SHARPE_CLAMP)
        if sd > 1e-12
        else 0.0
    )
    dr = [x for x in r if x < 0]
    dsd = st.pstdev(dr) if len(dr) > 1 else 0.0
    sortino = (
        clip((mu / dsd) * math.sqrt(tpy), -SHARPE_CLAMP, SHARPE_CLAMP)
        if dsd > 1e-12
        else 0.0
    )
    calmar = (total_return / abs(mdd)) if mdd < 0 else 0.0
    avg_dur = sum(float(t["bars_held"]) for t in tr) / N

    return dict(
        n_trades=N,
        total_return=total_return,
        gross_edge=gross_edge,
        cost_burden=cost_burden,
        max_drawdown=mdd,
        win_rate=win_rate,
        profit_factor=pf,
        expectancy=expectancy,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        avg_trade_duration_bars=avg_dur,
    )
