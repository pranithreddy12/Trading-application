"""
run_deployment_governor.py — Standalone DeploymentGovernor runner.

Proactively promotes elite/validated strategies to paper trading via
tournament selection, then sweeps pending deployments to auto-approve
and execute paper mode deployments.

Usage:
    python scripts/run_deployment_governor.py [--cycles N]
"""

import asyncio
import argparse
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l7_meta.deployment_governor import DeploymentGovernor


async def print_gov_report(governor: DeploymentGovernor) -> None:
    """Print a deployment governance status report."""
    report = await governor.get_deployment_report()
    by_status = report.get("by_status", {})
    recent = report.get("recent_deployments", [])

    print("\n" + "=" * 70)
    print("  DEPLOYMENT GOVERNANCE REPORT")
    print("=" * 70)
    print(f"  {'Status':<30} {'Count'}")
    print(f"  {'-'*30} {'-'*6}")
    for status, count in sorted(by_status.items()):
        print(f"  {status:<30} {count}")
    print(f"  {'-'*30} {'-'*6}")
    if recent:
        print(f"\n  Recent deployments ({len(recent)}):")
        for dep in recent[:10]:
            print(
                f"    {dep['mode']:<12} {dep['status']:<20} "
                f"{dep['strategy_id'][:8]}... | {dep.get('proposed_by','')}"
            )
    else:
        print("\n  No recent deployments.")
    print("=" * 70 + "\n")


async def run_cycle(governor: DeploymentGovernor) -> dict:
    """Run one complete governance cycle: select, sweep, check."""
    result = {
        "selected": 0,
        "proposed": 0,
        "approved": 0,
        "executed": 0,
    }

    # Step 1: Capture pre-cycle counts
    async with governor.db.engine.connect() as conn:
        r_pending = await conn.execute(
            text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'pending_approval'")
        )
        r_paper = await conn.execute(
            text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'paper'")
        )
        pre_pending = r_pending.scalar()
        pre_paper = r_paper.scalar()

    # Step 2: Select and propose paper candidates via tournament
    await governor._select_and_promote_paper_candidates()

    async with governor.db.engine.connect() as conn:
        r = await conn.execute(
            text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'pending_approval'")
        )
        post_pending = r.scalar()
    result["proposed"] = post_pending - pre_pending
    result["selected"] = 1 if result["proposed"] > 0 else 0

    # Step 3: Sweep pending deployments (auto-approve + execute paper)
    await governor._sweep_pending_deployments()

    # Step 4: Measure delta for paper executions
    async with governor.db.engine.connect() as conn:
        r = await conn.execute(
            text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'paper'")
        )
        post_paper = r.scalar()
    result["executed"] = post_paper - pre_paper

    return result


async def main(cycles: int = 1):
    logger.info("=" * 60)
    logger.info("  DEPLOYMENT GOVERNOR — Paper Trading Promotion")
    logger.info(f"  Cycles: {cycles}")
    logger.info("=" * 60)

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    db_client = TimescaleClient(db_url=settings.database_url)
    await db_client.connect()

    # Check eligible strategies
    async with db_client.engine.connect() as conn:
        r = await conn.execute(
            text("""
                SELECT COUNT(*) FROM strategies s
                JOIN backtest_results b ON b.strategy_id = s.id
                WHERE s.status IN ('elite', 'validated')
                  AND b.composite_fitness > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM deployment_governance d
                      WHERE d.strategy_id = s.id::text
                        AND d.status IN ('pending_approval', 'approved',
                                         'paper', 'shadow', 'partial_live', 'live')
                  )
            """)
        )
        eligible = r.scalar()
        logger.info(f"Eligible strategies for promotion: {eligible}")

        # Show top candidates
        if eligible > 0:
            r2 = await conn.execute(
                text("""
                    SELECT s.name, s.status, b.composite_fitness, b.short_window_score, b.sharpe
                    FROM strategies s
                    JOIN backtest_results b ON b.strategy_id = s.id
                    WHERE s.status IN ('elite', 'validated')
                      AND b.composite_fitness > 0
                      AND NOT EXISTS (
                          SELECT 1 FROM deployment_governance d
                          WHERE d.strategy_id = s.id::text
                            AND d.status IN ('pending_approval', 'approved',
                                             'paper', 'shadow', 'partial_live', 'live')
                      )
                    ORDER BY b.composite_fitness DESC
                """)
            )
            print("\nEligible candidates:")
            for row in r2.fetchall():
                print(f"  {row[0][:40]:<42} status={row[1]:<20} fitness={row[2]:<8.2f} "
                      f"score={row[3]:<8.2f} sharpe={row[4]:<8.2f}")

    # Instantiate governor
    governor = DeploymentGovernor(
        redis_client=redis_client,
        db_client=db_client,
    )
    governor.status = "running"

    total_proposed = 0
    total_executed = 0

    for cycle in range(1, cycles + 1):
        logger.info(f"\n--- Cycle {cycle}/{cycles} ---")
        result = await run_cycle(governor)
        total_proposed += result["proposed"]
        total_executed += result["executed"]
        logger.info(
            f"Cycle {cycle}: selected={result['selected']}, "
            f"proposed={result['proposed']}, "
            f"total_executed={result['executed']}"
        )

    # Final report
    await print_gov_report(governor)

    # Show deployment_mode on strategies
    async with db_client.engine.connect() as conn:
        r = await conn.execute(
            text("""
                SELECT deployment_mode, COUNT(*) as cnt
                FROM strategies
                WHERE deployment_mode IS NOT NULL
                GROUP BY deployment_mode
                ORDER BY cnt DESC
            """)
        )
        modes = r.fetchall()
        if modes:
            print("Deployment modes on strategies:")
            for row in modes:
                print(f"  {row[0]}: {row[1]}")

        r2 = await conn.execute(
            text("""
                SELECT s.name, s.deployment_mode, d.status, d.mode
                FROM strategies s
                JOIN deployment_governance d ON d.strategy_id = s.id::text
                ORDER BY d.proposed_at DESC
                LIMIT 10
            """)
        )
        rows = r2.fetchall()
        if rows:
            print("\nPromoted strategies:")
            for row in rows:
                name = row[0][:40] if row[0] else "?"
                dep_mode = row[1] or "-"
                gov_status = row[2] or "?"
                gov_mode = row[3] or "?"
                print(f"  {name:<42} dep_mode={dep_mode:<12} gov_status={gov_status:<20} gov_mode={gov_mode:<12}")

    logger.info("=" * 60)
    logger.info(f"  SUMMARY: {total_proposed} proposed, {total_executed} executed")
    logger.info("=" * 60)

    await redis_client.aclose()
    await db_client.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeploymentGovernor Launcher")
    parser.add_argument("--cycles", type=int, default=1, help="Number of governance cycles")
    args = parser.parse_args()
    asyncio.run(main(args.cycles))
