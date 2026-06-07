"""P6 T8 — Reconciliation & reporting: legacy vs v1 shadow outputs.

READ-ONLY. Compares the legacy stack (backtest_results + strategies.status) against
the v1 shadow tables (ledger_metrics_v1 / strategy_scores_v1 / validator_results_v1)
and produces four reports: metric drift, fitness ranking, validator transition
matrix, population summary. Modifies nothing.

The compute layer is pure (operates on plain row dicts) so it is unit-testable
without a DB; ReconciliationService just fetches rows (read-only) and delegates.

NOTE on max_drawdown drift: legacy stores drawdown as PERCENT (×100), shadow as a
FRACTION (P1 spec). The drift for that metric is therefore expected (~−99% pct
delta) and reflects the documented semantic change, not an error.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

# (label, legacy_key, shadow_key)
METRICS = [
    ("sharpe", "legacy_sharpe", "sharpe_v1"),
    ("win_rate", "legacy_win_rate", "win_rate_v1"),
    ("profit_factor", "legacy_profit_factor", "profit_factor_v1"),
    ("max_drawdown", "legacy_max_drawdown", "max_drawdown_v1"),
]

# metrics whose legacy↔shadow drift is expected by design (semantic change)
EXPECTED_DRIFT = {"max_drawdown"}


def to_float(v) -> Optional[float]:
    """Coerce DB NUMERIC (Decimal) / text to float; None passes through."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pct_delta(legacy: Optional[float], shadow: Optional[float]) -> Optional[float]:
    if legacy is None or shadow is None or legacy == 0:
        return None
    return (shadow - legacy) / abs(legacy) * 100.0


def summarize_distribution(values: Sequence[Optional[float]]) -> Optional[dict]:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    n = len(v)
    q = lambda p: v[min(n - 1, int(p * n))]
    return {
        "n": n,
        "min": v[0],
        "p25": q(0.25),
        "median": v[n // 2],
        "mean": sum(v) / n,
        "p75": q(0.75),
        "max": v[-1],
    }


def compute_metric_drift(rows: Sequence[dict]) -> dict:
    """Per-strategy and distribution-level legacy↔shadow deltas for each metric."""
    per_strategy: list[dict] = []
    dist: dict = {}
    for label, lk, sk in METRICS:
        abs_deltas, pct_deltas = [], []
        for r in rows:
            legacy = to_float(r.get(lk))
            shadow = to_float(r.get(sk))
            ad = (shadow - legacy) if (legacy is not None and shadow is not None) else None
            pd = pct_delta(legacy, shadow)
            abs_deltas.append(ad)
            pct_deltas.append(pd)
            per_strategy.append({
                "strategy_id": r.get("strategy_id"),
                "metric": label,
                "legacy": legacy,
                "shadow": shadow,
                "abs_delta": ad,
                "pct_delta": pd,
                "expected_drift": label in EXPECTED_DRIFT,
            })
        dist[label] = {
            "abs": summarize_distribution(abs_deltas),
            "pct": summarize_distribution(pct_deltas),
            "expected_drift": label in EXPECTED_DRIFT,
        }
    return {"per_strategy": per_strategy, "distribution": dist}


def rank_by_fitness(rows: Sequence[dict]) -> list[dict]:
    """Strategies ranked by deploy_fitness desc, then research_fitness desc."""
    enriched = [
        {
            "strategy_id": r.get("strategy_id"),
            "deploy_fitness": to_float(r.get("deploy_fitness")),
            "research_fitness": to_float(r.get("research_fitness")),
            "status_v1": r.get("status_v1"),
            "n_trades_v1": r.get("n_trades_v1"),
        }
        for r in rows
    ]
    enriched.sort(
        key=lambda x: (
            x["deploy_fitness"] if x["deploy_fitness"] is not None else float("-inf"),
            x["research_fitness"] if x["research_fitness"] is not None else float("-inf"),
        ),
        reverse=True,
    )
    for i, e in enumerate(enriched, start=1):
        e["rank"] = i
    return enriched


def compute_transition_matrix(rows: Sequence[dict]) -> dict:
    """legacy status -> shadow status_v1 transition counts."""
    counts = Counter((r.get("legacy_status"), r.get("status_v1")) for r in rows)
    transitions = [
        {"legacy_status": lg, "status_v1": sv, "count": c}
        for (lg, sv), c in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
    legacy_states = sorted({r.get("legacy_status") for r in rows}, key=lambda x: (x is None, x))
    shadow_states = sorted({r.get("status_v1") for r in rows}, key=lambda x: (x is None, x))
    matrix = {lg: {sv: counts.get((lg, sv), 0) for sv in shadow_states} for lg in legacy_states}
    return {"transitions": transitions, "matrix": matrix,
            "legacy_states": legacy_states, "shadow_states": shadow_states}


def compute_population_summary(rows: Sequence[dict], legacy_status_counts: dict) -> dict:
    """Counts by legacy status (full pop) and shadow status (reconciled set) + coverage."""
    shadow_counts = Counter(r.get("status_v1") for r in rows)
    present = sum(1 for r in rows if r.get("coverage_complete") is True)
    missing = sum(1 for r in rows if not r.get("coverage_complete"))
    return {
        "reconciled_strategies": len(rows),
        "legacy_status_counts": dict(legacy_status_counts),
        "shadow_status_counts": dict(shadow_counts),
        "coverage": {"present": present, "missing": missing},
    }


def _fmt(x) -> str:
    return "" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def build_csv_tables(report: dict) -> dict:
    """Pure: return {filename: (header, rows)} for CSV export."""
    tables: dict = {}

    # 1. metric drift (per strategy)
    hdr = ["strategy_id", "metric", "legacy", "shadow", "abs_delta", "pct_delta", "expected_drift"]
    tables["metric_drift.csv"] = (hdr, [
        [d["strategy_id"], d["metric"], d["legacy"], d["shadow"], d["abs_delta"], d["pct_delta"], d["expected_drift"]]
        for d in report["metric_drift"]["per_strategy"]
    ])

    # 1b. metric drift distribution
    hdr = ["metric", "stat", "abs_delta", "pct_delta", "expected_drift"]
    drows = []
    for metric, blocks in report["metric_drift"]["distribution"].items():
        a, p = blocks.get("abs") or {}, blocks.get("pct") or {}
        for stat in ("n", "min", "p25", "median", "mean", "p75", "max"):
            drows.append([metric, stat, a.get(stat), p.get(stat), blocks.get("expected_drift")])
    tables["metric_drift_distribution.csv"] = (hdr, drows)

    # 2. fitness ranking
    hdr = ["rank", "strategy_id", "deploy_fitness", "research_fitness", "status_v1", "n_trades_v1"]
    tables["fitness_ranking.csv"] = (hdr, [
        [e["rank"], e["strategy_id"], e["deploy_fitness"], e["research_fitness"], e["status_v1"], e["n_trades_v1"]]
        for e in report["fitness_ranking"]
    ])

    # 3. validator transitions
    hdr = ["legacy_status", "status_v1", "count"]
    tables["validator_transitions.csv"] = (hdr, [
        [t["legacy_status"], t["status_v1"], t["count"]] for t in report["validator_transitions"]["transitions"]
    ])

    # 4. population summary
    hdr = ["category", "key", "count"]
    ps = report["population_summary"]
    prows = []
    for k, v in ps["legacy_status_counts"].items():
        prows.append(["legacy_status", k, v])
    for k, v in ps["shadow_status_counts"].items():
        prows.append(["shadow_status", k, v])
    prows.append(["coverage", "present", ps["coverage"]["present"]])
    prows.append(["coverage", "missing", ps["coverage"]["missing"]])
    prows.append(["meta", "reconciled_strategies", ps["reconciled_strategies"]])
    tables["population_summary.csv"] = (hdr, prows)

    return tables


def build_console_report(report: dict, top_n: int = 10) -> str:
    """Pure: human-readable console summary."""
    L = []
    L.append("=" * 70)
    L.append(f"P6 T8 - RECONCILIATION REPORT (legacy vs v1 shadow)  rows={report['row_count']}")
    L.append("=" * 70)

    L.append("\n[1] METRIC DRIFT - distribution of (shadow - legacy):")
    L.append(f"    {'metric':14}{'n':>5}{'med_abs':>12}{'med_pct%':>12}  note")
    for metric, b in report["metric_drift"]["distribution"].items():
        a, p = b.get("abs") or {}, b.get("pct") or {}
        note = "EXPECTED (pct->frac)" if b.get("expected_drift") else ""
        L.append(f"    {metric:14}{a.get('n', 0):>5}{_fmt(a.get('median')):>12}{_fmt(p.get('median')):>12}  {note}")

    L.append(f"\n[2] FITNESS RANKING - top {top_n} by deploy_fitness:")
    L.append(f"    {'rank':>4}{'strategy':>12}{'deploy':>10}{'research':>10}  status_v1")
    for e in report["fitness_ranking"][:top_n]:
        sid = (e["strategy_id"] or "")[:8]
        L.append(f"    {e['rank']:>4}{sid:>12}{_fmt(e['deploy_fitness']):>10}{_fmt(e['research_fitness']):>10}  {e['status_v1']}")

    L.append("\n[3] VALIDATOR TRANSITION MATRIX (legacy -> status_v1):")
    vt = report["validator_transitions"]
    shadow_states = vt["shadow_states"]
    corner = "legacy / shadow"
    L.append("    " + f"{corner:>22}" + "".join(f"{(s or 'NULL')[:14]:>16}" for s in shadow_states))
    for lg in vt["legacy_states"]:
        row = vt["matrix"][lg]
        L.append("    " + f"{(lg or 'NULL'):>22}" + "".join(f"{row[s]:>16}" for s in shadow_states))

    L.append("\n[4] POPULATION SUMMARY:")
    ps = report["population_summary"]
    L.append(f"    reconciled strategies: {ps['reconciled_strategies']}")
    L.append(f"    coverage present/missing: {ps['coverage']['present']} / {ps['coverage']['missing']}")
    L.append("    legacy status counts (full population):")
    for k, v in sorted(ps["legacy_status_counts"].items(), key=lambda kv: -kv[1]):
        L.append(f"        {k:24} {v}")
    L.append("    shadow status counts (reconciled set):")
    for k, v in sorted(ps["shadow_status_counts"].items(), key=lambda kv: -kv[1]):
        L.append(f"        {str(k):24} {v}")
    L.append("=" * 70)
    return "\n".join(L)


class ReconciliationService:
    """Read-only orchestration over injected `db`."""

    def __init__(self, db):
        self.db = db

    async def generate(self) -> dict:
        """Fetch rows (read-only) and build all four reports."""
        rows = await self.db.get_reconciliation_rows()
        legacy_counts = await self.db.get_legacy_status_counts()
        return {
            "metric_drift": compute_metric_drift(rows),
            "fitness_ranking": rank_by_fitness(rows),
            "validator_transitions": compute_transition_matrix(rows),
            "population_summary": compute_population_summary(rows, legacy_counts),
            "row_count": len(rows),
        }
