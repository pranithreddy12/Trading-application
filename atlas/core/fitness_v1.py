"""P6 T3 — fitness_v1: P2 deploy/research fitness. PURE (no DB).

Faithful port of the FROZEN P2 operating point (scratch/P2_FITNESS_DESIGN.md
Part C + scratch/p2_calibration_sweep.py), consuming ledger_metrics_v1.

Two scores:
  research_fitness = 100 · Q          (smooth gradient; never gated to 0)
  deploy_fitness   = 100 · Q · M      (multiplicatively gated; deployability)

Quality core   Q = 0.60·PERFORMANCE + 0.40·ROBUSTNESS
Deployability  M = sig_gate · overfit_gate · cost_gate

FROZEN operating point (do NOT change — handoff + P2 Part C):
  cost_gate = retention^0.75 · churn   (COST_EXP = 0.75, frozen calibration)
  overfit_cutoff (OP_TOL) = 0.5
  deploy_threshold = 35  (consumed by P3 — NOT applied here; this module only scores)

FROZEN sub-parameters (from the calibration sweep — the values the sim ran):
  SHARPE_TARGET=2.0, E_TARGET=0.001, DD_TOL=0.25,
  N_HARD=10, N_FULL=100, TPD_OK=20, TPD_MAX=200

The significance-gate shape (N_HARD→N_FULL ramp) is P2's SOFT down-weight inside
deploy_fitness; P3 owns the separate HARD min-trades status floor. A strategy with
fewer than N_FULL(=100) trades is therefore structurally down-weighted here even
if its raw metrics are excellent — this is intended, not a bug.
"""
from __future__ import annotations

import math
import statistics as st
from typing import Mapping, Optional, Sequence

from atlas.core.ledger_metrics_v1 import ROUNDTRIP, SIZE, compute_ledger_metrics

# Frozen P2 parameters
SHARPE_TARGET: float = 2.0
E_TARGET: float = 0.001
DD_TOL: float = 0.25
OP_TOL: float = 0.5          # overfit_cutoff (frozen)
N_HARD: int = 10
N_FULL: int = 100
TPD_OK: float = 20.0
TPD_MAX: float = 200.0
COST_EXP: float = 0.75       # cost_gate = retention^0.75 · churn (frozen calibration)
DEPLOY_THRESHOLD: float = 35.0  # P3-consumed; exposed for reference, not applied here


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _zero_result(metrics: dict, reason: str) -> dict:
    return dict(
        research_fitness=0.0,
        deploy_fitness=0.0,
        Q=0.0,
        M=0.0,
        perf_Q=0.0,
        robust_Q=0.0,
        sig_gate=0.0,
        overfit_gate=0.0,
        cost_gate=0.0,
        n_trades=int(metrics.get("n_trades", 0)),
        insufficient=True,
        reason=reason,
        metrics=metrics,
    )


def compute_fitness(
    trades: Sequence[Mapping],
    *,
    walk_forward: Optional[float],
    monte_carlo: Optional[float],
    regime: Optional[float],
    overfit: Optional[float],
    metrics: Optional[dict] = None,
) -> dict:
    """Compute research/deploy fitness for one strategy.

    Args:
        trades: ledger trade list (see ledger_metrics_v1.compute_ledger_metrics).
        walk_forward, monte_carlo, regime: advanced-validator scores ∈ [0,1] or None.
        overfit: overfit_probability ∈ [0,1] or None (None → provisional 0.3 gate).
        metrics: optional precomputed ledger_metrics_v1 (recomputed if omitted).

    Returns:
        dict with research_fitness, deploy_fitness, Q, M and the gate components.
        Strategies with < 2 trades return an all-zero result (insufficient=True).
    """
    m = metrics if metrics is not None else compute_ledger_metrics(trades)
    if m.get("n_trades", 0) < 2:
        return _zero_result(m, "n_trades < 2")

    # ---- Quality core Q ----
    sharpe_s = _clip(m["sharpe"] / SHARPE_TARGET)
    pf_s = _clip((m["profit_factor"] - 1.0) / 1.0)
    exp_s = _clip(m["expectancy"] / E_TARGET)
    dd_s = _clip(1.0 + m["max_drawdown"] / DD_TOL)
    perf_Q = (0.22 * sharpe_s + 0.16 * pf_s + 0.12 * exp_s + 0.10 * dd_s) / 0.60
    robust_Q = (
        0.18 * (walk_forward or 0.0)
        + 0.12 * (monte_carlo or 0.0)
        + 0.10 * (regime or 0.0)
    ) / 0.40
    Q = 0.60 * perf_Q + 0.40 * robust_Q

    # ---- Deployability gate M ----
    N = m["n_trades"]
    n_gate = 0.0 if N < N_HARD else _clip((N - N_HARD) / (N_FULL - N_HARD))

    tr = sorted(trades, key=lambda t: t["entry_time"])
    r = [(float(t["pnl_pct"]) - ROUNDTRIP) * SIZE for t in tr]
    mu = st.mean(r)
    sd = st.pstdev(r) if len(r) > 1 else 0.0
    t_stat = (mu / sd) * math.sqrt(N) if sd > 1e-12 else 0.0
    psr_gate = _clip((_phi(t_stat) - 0.5) / 0.45)
    sig_gate = n_gate * psr_gate

    overfit_gate = 0.3 if overfit is None else _clip(1.0 - overfit / OP_TOL)

    ge = m["gross_edge"]
    retention = 0.0 if ge <= 0 else _clip(m["total_return"] / ge)
    span_days = max(
        (tr[-1]["exit_time"] - tr[0]["entry_time"]).total_seconds() / 86400.0, 0.5
    )
    tpd = N / span_days
    churn = (
        _clip(1.0 - (tpd - TPD_OK) / (TPD_MAX - TPD_OK)) if tpd > TPD_OK else 1.0
    )
    cost_gate = (retention ** COST_EXP) * churn

    M = sig_gate * overfit_gate * cost_gate

    return dict(
        research_fitness=100.0 * Q,
        deploy_fitness=100.0 * Q * M,
        Q=Q,
        M=M,
        perf_Q=perf_Q,
        robust_Q=robust_Q,
        sig_gate=sig_gate,
        overfit_gate=overfit_gate,
        cost_gate=cost_gate,
        n_trades=N,
        insufficient=False,
        reason="",
        metrics=m,
    )
