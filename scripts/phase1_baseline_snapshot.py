"""
Phase 1 — Baseline Snapshot: Collect current metrics before running IdeatorV2 tests.
Run: python scripts/phase1_baseline_snapshot.py
"""

import asyncio
import json
from datetime import datetime

import asyncpg


async def main():
    dsn = "postgresql://postgres:password@localhost:5433/atlas"
    conn = await asyncpg.connect(dsn)

    try:
        # Query 1: Status distribution
        rows = await conn.fetch(
            "SELECT status, COUNT(*)::int as cnt FROM strategies GROUP BY status ORDER BY cnt DESC"
        )
        print("=== Status Distribution ===")
        total_all = 0
        status_map = {}
        for r in rows:
            print(f"  {r['status']}: {r['cnt']}")
            status_map[r["status"]] = r["cnt"]
            total_all += r["cnt"]
        print(f"  TOTAL: {total_all}")

        # Query 2: Pass rate
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status IN ('validated','research_candidate','repair_candidate')) * 100.0 / NULLIF(COUNT(*), 0) AS pass_rate_pct
            FROM strategies
        """)
        pass_rate = float(row["pass_rate_pct"]) if row and row["pass_rate_pct"] else 0.0
        print(f"\n=== Pass Rate ===")
        print(f"  Pass Rate %: {pass_rate:.2f}")

        # Query 3: Failure type breakdown
        rows = await conn.fetch("""
            SELECT
                CASE
                    WHEN COALESCE(parameters->>'validation_notes','') LIKE '%high_churn_cost_trap%' THEN 'cost_trap'
                    WHEN COALESCE(parameters->>'validation_notes','') LIKE '%Total trades 0%' THEN 'zero_trade'
                    ELSE 'other'
                END AS failure_type,
                COUNT(*)::int as cnt
            FROM strategies
            WHERE status='failed_validation'
            GROUP BY 1
        """)
        print(f"\n=== Failure Type Breakdown (failed_validation only) ===")
        failure_map = {}
        for r in rows:
            failure_map[r["failure_type"]] = r["cnt"]
            print(f"  {r['failure_type']}: {r['cnt']}")

        # Additional useful metrics
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='pending_backtest'"
        )
        pending_bt = int(row["cnt"]) if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='validated'"
        )
        validated = int(row["cnt"]) if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='research_candidate'"
        )
        research_candidate = int(row["cnt"]) if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='failed_validation'"
        )
        failed_validation = int(row["cnt"]) if row else 0

        print(f"\n=== Summary Metrics ===")
        print(f"  Pass Rate %:         {pass_rate:.2f}")
        print(f"  Failed Validation:   {failed_validation}")
        print(f"  Pending Backtest:    {pending_bt}")
        print(f"  Cost Trap Failures:  {failure_map.get('cost_trap', 0)}")
        print(f"  Zero Trade Failures: {failure_map.get('zero_trade', 0)}")
        print(f"  Research Candidate:  {research_candidate}")
        print(f"  Validated:           {validated}")

        # V2 strategies count
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int as cnt FROM strategies WHERE generation_batch IS NOT NULL"
        )
        v2_count = int(row["cnt"]) if row else 0
        print(f"  Strategies with generation_batch (V2): {v2_count}")

        # Archetype diversity
        rows = await conn.fetch("""
            SELECT
                COALESCE(parameters->>'archetype', 'unknown') as archetype,
                COUNT(*)::int as cnt
            FROM strategies
            GROUP BY 1
            ORDER BY cnt DESC
        """)
        print(f"\n=== Archetype Diversity ===")
        for r in rows:
            print(f"  {r['archetype']}: {r['cnt']}")

        # Also check pending_validation and other pipeline statuses
        for s in [
            "pending_code",
            "pending_validation",
            "pending_backtest",
            "code_failed",
            "backtest_failed",
        ]:
            row = await conn.fetchrow(
                f"SELECT COUNT(*)::int as cnt FROM strategies WHERE status='{s}'"
            )
            status_map[s] = int(row["cnt"]) if row else 0

        # Write snapshot to file
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_strategies": total_all,
            "status_distribution": {k: int(v) for k, v in status_map.items()},
            "pass_rate_pct": round(pass_rate, 2),
            "failed_validation": failed_validation,
            "pending_backtest": pending_bt,
            "validated": validated,
            "research_candidate": research_candidate,
            "failure_breakdown": {k: int(v) for k, v in failure_map.items()},
            "v2_strategies": v2_count,
        }
        with open("logs/baseline_snapshot.json", "w") as f:
            json.dump(snapshot, f, indent=2, default=str)
        print(f"\nSnapshot saved to logs/baseline_snapshot.json")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
