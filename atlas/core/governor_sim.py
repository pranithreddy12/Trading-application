"""P6 T10 — Shadow governor validation (simulation only).

Applies the FROZEN P4 governor policy to the shadow population, READ-ONLY. It
simulates eligibility, promotion selection, and capital allocation; it writes
NOTHING (no strategies.status, strategy_performance, deployment tables) and does
NOT touch the production governor or switch authority.

FROZEN P4 policy (scratch/P4_GOVERNOR_DESIGN.md):
  ELIGIBILITY    : status in {validated, elite}                       (P3-certified)
  DEFENSIVE GATE : fresh re-check — n_trades >= MIN_FLOOR
                   AND overfit < OP_CUT AND coverage complete
                   AND deploy_fitness >= DEPLOY_THRESH                (defense-in-depth)
  SELECTION      : rank by deploy_fitness, max 10 concurrent
  ALLOCATION     : deploy-weighted; per-strategy cap 20%, family cap 40%,
                   per-position notional $5k (execution layer)

Thresholds consumed from the frozen modules (not redefined here):
  MIN_FLOOR=50, DEPLOY_THRESH=35 (validator_policy_v1); OP_CUT=0.5 (fitness_v1 OP_TOL).

Allocation note: P4 §5 left freed-capital redistribution as an open implementation
choice; this sim uses the CONSERVATIVE interpretation (caps bind; unused capital
stays unallocated).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional, Sequence

from atlas.core.fitness_v1 import OP_TOL as OP_CUT
from atlas.core.validator_policy_v1 import DEPLOY_THRESH, MIN_FLOOR

MAX_CONCURRENT = 10
DEFAULT_BUDGET = 50_000.0
PER_STRATEGY_CAP = 0.20      # 20% of budget
FAMILY_CAP = 0.40            # 40% of budget
NOTIONAL_CAP = 5_000.0       # per-position execution cap (reported)

ELIGIBLE_STATUSES = ("validated", "elite")

# ordered rejection gates (first failure wins -> clean partition)
REJECTION_ORDER = [
    "not_certified",
    "underpowered",
    "coverage_incomplete",
    "overfit",
    "deploy_below_threshold",
]


def _f(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def evaluate_eligibility(row: dict) -> tuple[bool, Optional[str]]:
    """Frozen P4 eligibility + fresh defensive gate. Returns (eligible, first_failing_gate).

    overfit is optional: when absent (real shadow rows don't denormalize it) the
    explicit overfit gate is skipped — it is enforced transitively by the
    deploy_fitness gate (overfit>=0.5 => deploy_fitness=0 < threshold)."""
    status = row.get("status_v1") or row.get("status")
    if status not in ELIGIBLE_STATUSES:
        return False, "not_certified"
    if int(row.get("n_trades") or 0) < MIN_FLOOR:
        return False, "underpowered"
    if not row.get("coverage_complete"):
        return False, "coverage_incomplete"
    overfit = row.get("overfit")
    if overfit is not None and _f(overfit) >= OP_CUT:
        return False, "overfit"
    if _f(row.get("deploy_fitness")) < DEPLOY_THRESH:
        return False, "deploy_below_threshold"
    return True, None


def simulate_promotion(eligible: Sequence[dict], max_concurrent: int = MAX_CONCURRENT) -> list[dict]:
    """Select up to max_concurrent eligible strategies, ranked by deploy_fitness desc."""
    ranked = sorted(eligible, key=lambda r: _f(r.get("deploy_fitness")), reverse=True)
    return ranked[:max_concurrent]


def simulate_allocation(
    selected: Sequence[dict],
    budget: float = DEFAULT_BUDGET,
    per_strategy_cap: float = PER_STRATEGY_CAP,
    family_cap: float = FAMILY_CAP,
) -> dict:
    """Deploy-weighted allocation with per-strategy + family caps (conservative)."""
    if not selected:
        return {
            "allocations": [], "total_allocated": 0.0, "budget": budget,
            "per_strategy_cap_amt": per_strategy_cap * budget,
            "family_cap_amt": family_cap * budget, "family_totals": {},
            "notional_cap": NOTIONAL_CAP,
        }
    total_deploy = sum(_f(s.get("deploy_fitness")) for s in selected) or 1.0
    ps_cap_amt = per_strategy_cap * budget
    fam_cap_amt = family_cap * budget

    alloc: dict = {}
    for s in selected:
        raw = _f(s.get("deploy_fitness")) / total_deploy * budget
        alloc[s["strategy_id"]] = min(raw, ps_cap_amt)

    # family cap: scale members down proportionally if family total exceeds cap
    fam_members: dict = defaultdict(list)
    for s in selected:
        fam_members[s.get("family") or "_none"].append(s["strategy_id"])
    for members in fam_members.values():
        fam_total = sum(alloc[m] for m in members)
        if fam_total > fam_cap_amt and fam_total > 0:
            scale = fam_cap_amt / fam_total
            for m in members:
                alloc[m] *= scale

    allocations = [
        {
            "strategy_id": s["strategy_id"],
            "family": s.get("family"),
            "deploy_fitness": _f(s.get("deploy_fitness")),
            "capital": round(alloc[s["strategy_id"]], 2),
        }
        for s in selected
    ]
    family_totals = {
        f: round(sum(alloc[m] for m in members), 2) for f, members in fam_members.items()
    }
    return {
        "allocations": allocations,
        "total_allocated": round(sum(alloc.values()), 2),
        "budget": budget,
        "per_strategy_cap_amt": ps_cap_amt,
        "family_cap_amt": fam_cap_amt,
        "family_totals": family_totals,
        "notional_cap": NOTIONAL_CAP,
    }


def simulate_governor(
    rows: Sequence[dict],
    budget: float = DEFAULT_BUDGET,
    max_concurrent: int = MAX_CONCURRENT,
) -> dict:
    """Full frozen-P4 pass over a population: eligibility -> promotion -> allocation."""
    eligible, rejections = [], Counter()
    for r in rows:
        ok, reason = evaluate_eligibility(r)
        if ok:
            eligible.append(r)
        else:
            rejections[reason] += 1
    promoted = simulate_promotion(eligible, max_concurrent)
    allocation = simulate_allocation(promoted, budget)
    return {
        "population": len(rows),
        "eligible_count": len(eligible),
        "promoted_count": len(promoted),
        "allocated_capital": allocation["total_allocated"],
        "rejection_breakdown": {k: rejections.get(k, 0) for k in REJECTION_ORDER if rejections.get(k)},
        "eligible": eligible,
        "promoted": promoted,
        "allocation": allocation,
    }


def force_stale_status(rows: Sequence[dict], status: str = "validated") -> list[dict]:
    """Defense-in-depth helper: stamp a (stale) legacy status on every row so the
    fresh defensive gate is the only thing standing between them and promotion."""
    return [{**r, "status_v1": status} for r in rows]


def build_governor_report(result: dict, title: str = "") -> str:
    L = []
    L.append("=" * 66)
    L.append(f"P6 T10 - SHADOW GOVERNOR {title}".rstrip())
    L.append("=" * 66)
    L.append(f"  population        {result['population']}")
    L.append(f"  eligible          {result['eligible_count']}")
    L.append(f"  promoted          {result['promoted_count']}")
    L.append(f"  allocated capital  ${result['allocated_capital']:,.2f}")
    L.append("  rejection breakdown (first failing gate):")
    if result["rejection_breakdown"]:
        for k, v in result["rejection_breakdown"].items():
            L.append(f"      {k:24} {v}")
    else:
        L.append("      (none)")
    alloc = result["allocation"]
    if alloc["allocations"]:
        L.append(f"  allocation (budget ${alloc['budget']:,.0f}, per-strat cap "
                 f"${alloc['per_strategy_cap_amt']:,.0f}, family cap ${alloc['family_cap_amt']:,.0f}):")
        for a in alloc["allocations"]:
            L.append(f"      {a['strategy_id'][:8]}  deploy={a['deploy_fitness']:.1f}  "
                     f"fam={a['family']}  ${a['capital']:,.2f}")
        L.append(f"      family totals: {alloc['family_totals']}")
    L.append("=" * 66)
    return "\n".join(L)


class GovernorSimulator:
    """Read-only orchestration over injected `db` (the three v1 tables)."""

    def __init__(self, db):
        self.db = db

    async def run(self, budget: float = DEFAULT_BUDGET) -> dict:
        rows = await self.db.get_shadow_governor_rows()
        return simulate_governor(rows, budget)

    async def run_defense_in_depth(self, budget: float = DEFAULT_BUDGET) -> dict:
        """Force stale 'validated' status on the real population and confirm the
        fresh defensive gate still rejects (P4-H5 on live data)."""
        rows = await self.db.get_shadow_governor_rows()
        return simulate_governor(force_stale_status(rows, "validated"), budget)
