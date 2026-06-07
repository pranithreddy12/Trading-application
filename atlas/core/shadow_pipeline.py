"""P6 T7 — Shadow computation pipeline.

Reads legacy strategy data, runs the FROZEN canonical functions (P1 metrics,
P2 fitness, P3 validator policy), and writes the results to the ADDITIVE *_v1
shadow tables ONLY. It NEVER writes any legacy surface:
  - strategies.status            (untouched)
  - backtest_results             (read-only)
  - composite_fitness_score      (untouched)
  - passed_validation            (untouched)

It performs NO authority switch, NO cutover, and is wired into NO live consumer.
It orchestrates injected storage methods + the pure core modules; it issues no
SQL and constructs no DB engine itself (so it is unit-testable with a fake db).

Per-strategy flow (one row per latest backtest window, keyed strategy_id+window):
  1. load latest backtest_results window  -> (start_date, end_date)
  2. load backtest_trades                  -> ledger
  3. compute_ledger_metrics (P1)
  4. compute fitness + classify (P2 + P3) via validator_policy_v1.evaluate
  5. write ledger_metrics_v1 / strategy_scores_v1 / validator_results_v1

Population semantics match the frozen sims: strategies with >= 2 trades are
processed; fewer-than-2 are skipped (the frozen reference population). Structural
gating is left at the sim default (structural_ok=True) so shadow output reproduces
the validated P3 sim; real structural-sanity wiring belongs to consumer
integration (a later task), not the shadow pipeline.
"""
from __future__ import annotations

from typing import Callable, Iterable, Mapping, Optional

from atlas.core.ledger_metrics_v1 import compute_ledger_metrics
from atlas.core.validator_policy_v1 import evaluate

MIN_TRADES = 2  # frozen reference population (>= 2 trades)


def _to_float(v):
    """DB→pure boundary coercion: NUMERIC columns arrive as decimal.Decimal; the
    frozen pure functions expect float (the sims cast at this same boundary, e.g.
    p2_fitness_sim.py:81). None passes through (coverage gap)."""
    return float(v) if v is not None else None


def map_advanced(advanced_raw: Optional[Mapping]) -> dict:
    """Map get_advanced_validation() keys -> the policy/fitness key names used by
    the frozen sims (None where a validator produced no row -> coverage gap)."""
    a = advanced_raw or {}
    return {
        "walk_forward": _to_float(a.get("walk_forward_score")),
        "monte_carlo": _to_float(a.get("monte_carlo_survival_score")),
        "regime": _to_float(a.get("regime_survival_score")),
        "overfit": _to_float(a.get("overfit_probability")),
    }


class ShadowComputationPipeline:
    """Orchestrates shadow computation over injected storage (`db`)."""

    def __init__(self, db):
        self.db = db

    async def process_strategy(self, strategy_id) -> dict:
        """Compute + persist v1 shadow outputs for one strategy. Returns a record."""
        sid = str(strategy_id)
        rec: dict = {"strategy_id": sid, "written": False, "reason": None}

        window = await self.db.get_backtest_result(sid)
        if not window:
            rec["reason"] = "no_backtest_result"
            return rec
        start, end = window.get("start_date"), window.get("end_date")
        if start is None or end is None:
            rec["reason"] = "no_window_dates"
            return rec

        trades = await self.db.get_backtest_trades(sid)
        rec["n_trades"] = len(trades)
        if len(trades) < MIN_TRADES:
            rec["reason"] = "insufficient_trades"
            return rec

        metrics = compute_ledger_metrics(trades)
        advanced = map_advanced(await self.db.get_advanced_validation(sid))
        ev = evaluate(trades, advanced, structural_ok=True, metrics=metrics)
        fit = ev["fitness"]

        # WRITE: v1 shadow tables ONLY.
        await self.db.save_ledger_metrics_v1(sid, start, end, metrics)
        await self.db.save_strategy_scores_v1(sid, start, end, fit)
        await self.db.save_validator_result_v1(
            sid,
            start,
            end,
            {
                "status": ev["status"],
                "deploy_fitness": ev["deploy_fitness"],
                "research_fitness": ev["research_fitness"],
                "n_trades": ev["n_trades"],
                "coverage_complete": ev["coverage_complete"],
                "structural_ok": True,
            },
        )

        rec.update(
            written=True,
            status_v1=ev["status"],
            deploy_fitness=ev["deploy_fitness"],
            research_fitness=ev["research_fitness"],
            coverage_complete=ev["coverage_complete"],
        )
        return rec

    async def run_batch(
        self,
        strategy_ids: Iterable,
        *,
        progress_every: int = 0,
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """Process an explicit set of strategy_ids; return an aggregate summary.

        Failure isolation: a per-strategy exception is recorded and the batch
        continues. Progress: if progress_every>0 and progress_cb is given, the
        callback receives a counters snapshot every N processed (and once at end).
        """
        summary = {
            "processed": 0,
            "written": 0,
            "skipped": 0,
            "failed": 0,
            "ledger_rows": 0,
            "score_rows": 0,
            "validator_rows": 0,
            "by_status": {},
            "skips": {},
            "errors": [],
        }

        def _snapshot() -> dict:
            return {k: summary[k] for k in ("processed", "written", "skipped", "failed")}

        for sid in strategy_ids:
            summary["processed"] += 1
            try:
                rec = await self.process_strategy(sid)
            except Exception as e:  # never let one strategy abort the batch
                summary["failed"] += 1
                summary["errors"].append({"strategy_id": str(sid), "error": repr(e)})
            else:
                if rec.get("written"):
                    summary["written"] += 1
                    summary["ledger_rows"] += 1
                    summary["score_rows"] += 1
                    summary["validator_rows"] += 1
                    st = rec["status_v1"]
                    summary["by_status"][st] = summary["by_status"].get(st, 0) + 1
                else:
                    summary["skipped"] += 1
                    reason = rec.get("reason", "unknown")
                    summary["skips"][reason] = summary["skips"].get(reason, 0) + 1
            if progress_every and progress_cb and summary["processed"] % progress_every == 0:
                progress_cb(_snapshot())
        if progress_cb:
            progress_cb(_snapshot())  # final snapshot
        return summary

    async def replay_population(
        self,
        limit: Optional[int] = None,
        *,
        resume: bool = False,
        progress_every: int = 0,
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """Replay over the historical population (all strategies with a backtest).

        Idempotent (upserts). Resume-safe: with resume=True, strategies already
        present in validator_results_v1 are skipped so an interrupted run continues
        cleanly. Read-only on legacy.
        """
        ids = await self.db.get_strategy_ids_with_backtest_results(limit=limit)
        population_size = len(ids)
        resumed_skipped = 0
        if resume:
            done = set(await self.db.get_shadow_computed_strategy_ids())
            ids = [i for i in ids if i not in done]
            resumed_skipped = population_size - len(ids)
        summary = await self.run_batch(
            ids, progress_every=progress_every, progress_cb=progress_cb
        )
        summary["population_size"] = population_size
        summary["resumed_skipped"] = resumed_skipped
        return summary
