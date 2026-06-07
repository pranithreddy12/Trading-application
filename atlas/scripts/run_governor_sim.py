"""P6 T10 — Shadow governor validation command (read-only, simulation).

Runs three passes against the shadow population (the three v1 tables only):
  1. Real eligibility under frozen P4 policy.
  2. Defense-in-depth: force stale 'validated' status on the REAL population and
     confirm the fresh defensive gate still rejects everything.
  3. Synthetic positive control: a genuine-good, multi-family pool that SHOULD be
     promoted + allocated, proving caps (per-strategy 20%, family 40%, max 10) work.

Writes nothing. Does not touch the production governor / deployment paths.

Usage:
  python -m atlas.scripts.run_governor_sim
"""
import asyncio

from atlas.config.settings import settings
from atlas.core.governor_sim import (
    DEFAULT_BUDGET,
    GovernorSimulator,
    build_governor_report,
    simulate_governor,
)
from atlas.data.storage.timescale_client import TimescaleClient


def _synthetic_pool() -> list[dict]:
    """6 genuine-good validated strategies across 2 families (mean_reversion x4,
    momentum x2) -> family cap (40% = $20k) must bind on mean_reversion."""
    pool = []
    for i in range(4):
        pool.append(dict(strategy_id=f"mr_{i}", status_v1="validated", n_trades=150,
                         coverage_complete=True, overfit=0.1, deploy_fitness=60 - i,
                         family="mean_reversion"))
    for i in range(2):
        pool.append(dict(strategy_id=f"mo_{i}", status_v1="elite", n_trades=180,
                         coverage_complete=True, overfit=0.05, deploy_fitness=65 - i,
                         family="momentum"))
    return pool


def _stale_junk_pool() -> list[dict]:
    """Stale legacy 'validated'/'elite' status but each fails ONE fresh gate."""
    return [
        dict(strategy_id="stale_n1", status_v1="validated", n_trades=1, coverage_complete=True, overfit=0.1, deploy_fitness=60, family="x"),
        dict(strategy_id="stale_of", status_v1="validated", n_trades=200, coverage_complete=True, overfit=1.0, deploy_fitness=60, family="x"),
        dict(strategy_id="stale_cov", status_v1="elite", n_trades=200, coverage_complete=False, overfit=0.1, deploy_fitness=60, family="x"),
        dict(strategy_id="stale_dep", status_v1="validated", n_trades=200, coverage_complete=True, overfit=0.1, deploy_fitness=10, family="x"),
    ]


async def main() -> None:
    db = TimescaleClient(settings.database_url)
    await db.connect()
    sim = GovernorSimulator(db)

    # Pass 1 — real population
    real = await sim.run(budget=DEFAULT_BUDGET)
    print(build_governor_report(real, "[1] REAL POPULATION (status_v1 as-is)"))

    # Pass 2 — defense-in-depth on real data (force stale 'validated')
    dind = await sim.run_defense_in_depth(budget=DEFAULT_BUDGET)
    print("\n" + build_governor_report(dind, "[2] DEFENSE-IN-DEPTH (forced stale 'validated' on REAL pop)"))
    print(f"  >> forced {dind['population']} stale-validated; eligible after fresh re-gate = "
          f"{dind['eligible_count']} (expect 0)")

    # Pass 3a — synthetic stale-junk (P4-H5): each fails one fresh gate
    junk = simulate_governor(_stale_junk_pool(), budget=DEFAULT_BUDGET)
    print("\n" + build_governor_report(junk, "[3a] SYNTHETIC STALE-JUNK (each fails one gate)"))

    # Pass 3b — synthetic genuine-good positive control (P4-H3/H4): caps must hold
    good = simulate_governor(_synthetic_pool(), budget=DEFAULT_BUDGET)
    print("\n" + build_governor_report(good, "[3b] SYNTHETIC GENUINE-GOOD (positive control + caps)"))


if __name__ == "__main__":
    asyncio.run(main())
