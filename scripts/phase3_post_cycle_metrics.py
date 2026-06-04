"""
Phase 3 — Post-Cycle Metrics Collection
"""

import asyncio, json, sys
from datetime import datetime

import asyncpg


async def main():
    conn = await asyncpg.connect("postgresql://postgres:password@localhost:5433/atlas")

    # 1. Full status distribution
    rows = await conn.fetch(
        "SELECT status, COUNT(*)::int as cnt FROM strategies GROUP BY status ORDER BY cnt DESC"
    )
    status_map = {r["status"]: r["cnt"] for r in rows}
    total_all = sum(status_map.values())
    print("=== Post-Cycle Status Distribution ===")
    for k, v in sorted(status_map.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"  TOTAL: {total_all}")

    # 2. Pass rate
    row = await conn.fetchrow("""
        SELECT COUNT(*) FILTER (WHERE status IN ('validated','research_candidate','repair_candidate')) * 100.0 / NULLIF(COUNT(*), 0) AS pass_rate_pct
        FROM strategies
    """)
    pass_rate = float(row["pass_rate_pct"]) if row and row["pass_rate_pct"] else 0.0
    print(f"\nPass Rate: {pass_rate:.2f}%")

    # 3. Failure breakdown
    rows = await conn.fetch("""
        SELECT CASE
            WHEN COALESCE(parameters->>'validation_notes','') LIKE '%high_churn_cost_trap%' THEN 'cost_trap'
            WHEN COALESCE(parameters->>'validation_notes','') LIKE '%Total trades 0%' THEN 'zero_trade'
            ELSE 'other'
        END AS failure_type, COUNT(*)::int as cnt
        FROM strategies WHERE status='failed_validation' GROUP BY 1
    """)
    failure_map = {r["failure_type"]: r["cnt"] for r in rows}
    print("\n=== Failure Breakdown ===")
    for k, v in sorted(failure_map.items()):
        print(f"  {k}: {v}")

    # 4. New strategies created during test run
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE created_at > '2026-06-01T17:21:00Z'"
    )
    new_strategies = int(row["cnt"]) if row else 0
    print(f"\nNew strategies during test: {new_strategies}")

    # 5. V2 batch strategies
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE generation_batch IS NOT NULL"
    )
    v2_count = int(row["cnt"]) if row else 0
    print(f"V2 batch strategies: {v2_count}")

    # 6. Archetype diversity (from parameters->>'archetype')
    rows = await conn.fetch("""
        SELECT COALESCE(parameters->>'archetype', 'unknown') as archetype, COUNT(*)::int as cnt
        FROM strategies WHERE created_at > '2026-06-01T17:21:00Z'
        GROUP BY 1 ORDER BY cnt DESC
    """)
    print("\n=== Archetype Diversity (new strategies) ===")
    archetype_map = {}
    for r in rows:
        archetype_map[r["archetype"]] = r["cnt"]
        print(f"  {r['archetype']}: {r['cnt']}")
    if rows:
        max_pct = max(r["cnt"] for r in rows) / max(new_strategies, 1) * 100
        print(f"  Max archetype %: {max_pct:.1f}%")

    # 7. Pipeline throughput metrics
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='pending_backtest'"
    )
    pending_bt = int(row["cnt"]) if row else 0
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='pending_validation'"
    )
    pending_val = int(row["cnt"]) if row else 0
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='pending_code'"
    )
    pending_code = int(row["cnt"]) if row else 0
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='validated'"
    )
    validated = int(row["cnt"]) if row else 0
    row = await conn.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM strategies WHERE status='research_candidate'"
    )
    research_candidate = int(row["cnt"]) if row else 0
    print(f"\n=== Pipeline Metrics ===")
    print(f"  pending_code: {pending_code}")
    print(f"  pending_backtest: {pending_bt}")
    print(f"  pending_validation: {pending_val}")
    print(f"  validated: {validated}")
    print(f"  research_candidate: {research_candidate}")

    # 8. Count code_failed and backtest_failed
    code_failed = status_map.get("code_failed", 0)
    backtest_failed = status_map.get("backtest_failed", 0)
    print(f"  code_failed: {code_failed}")
    print(f"  backtest_failed: {backtest_failed}")

    # Save results
    snapshot = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_strategies": total_all,
        "status_distribution": {k: int(v) for k, v in status_map.items()},
        "pass_rate_pct": round(pass_rate, 2),
        "failure_breakdown": {k: int(v) for k, v in failure_map.items()},
        "new_strategies_during_test": new_strategies,
        "v2_batch_strategies": v2_count,
        "archetype_diversity_new": archetype_map,
    }
    with open("logs/post_cycle_snapshot.json", "w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    print(f"\nSaved to logs/post_cycle_snapshot.json")

    await conn.close()


asyncio.run(main())
