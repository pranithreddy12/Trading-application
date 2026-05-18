"""
run_mutation_children.py — Targeted backtest + validate for un-scored mutation children.

Finds all mutation children where child_composite_score IS NULL,
runs them through BacktestRunner + ValidatorAgent in sequence,
then calls mutation_backfill to populate scores.

Usage:
    python scripts/run_mutation_children.py
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text

from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient

# Inline backfill logic so we don't need a subprocess
BACKFILL_QUERY = """
    SELECT
        mm.id                                    AS mm_id,
        mm.parent_composite_score                AS parent_cs,
        (b.results->>'short_window_score')::NUMERIC AS child_cs
    FROM mutation_memory mm
    JOIN strategies s ON mm.child_strategy_id = s.id
    JOIN backtest_results b ON s.id = b.strategy_id
    WHERE
        mm.child_composite_score IS NULL
        AND b.results ? 'short_window_score'
        AND (b.results->>'short_window_score')::TEXT <> 'null'
"""

UPDATE_QUERY = """
    UPDATE mutation_memory
    SET
        child_composite_score = :child_cs,
        score_delta           = :score_delta,
        improved              = :improved
    WHERE id = :mm_id
"""


async def get_pending_children(db: TimescaleClient) -> list[dict]:
    """Fetch child strategies from mutation_memory where score not yet filled."""
    query = """
        SELECT DISTINCT
            s.id, s.name, s.code, s.parameters, s.normalized_strategy,
            s.status, s.created_at, s.author_agent
        FROM mutation_memory mm
        JOIN strategies s ON mm.child_strategy_id = s.id
        WHERE
            mm.child_composite_score IS NULL
            AND s.status IN ('pending_backtest', 'pending_validation', 'pending_code')
        ORDER BY s.created_at ASC
    """
    import json, decimal
    async with db.engine.connect() as conn:
        result = await conn.execute(text(query))
        rows = result.fetchall()
    out = []
    for r in rows:
        d = dict(r._mapping)
        for k, v in d.items():
            if isinstance(v, decimal.Decimal):
                d[k] = float(v)
        # Ensure UUIDs are plain strings — asyncpg returns UUID objects
        for uuid_key in ("id", "trace_id"):
            if uuid_key in d and d[uuid_key] is not None:
                d[uuid_key] = str(d[uuid_key])
        if isinstance(d.get("parameters"), str):
            try:
                d["parameters"] = json.loads(d["parameters"])
            except Exception:
                pass
        if isinstance(d.get("normalized_strategy"), str):
            try:
                d["normalized_strategy"] = json.loads(d["normalized_strategy"])
            except Exception:
                pass
        out.append(d)
    return out


def run_backfill_sync(engine) -> dict:
    """Synchronous backfill after backtest completes."""
    with engine.begin() as conn:
        rows = conn.execute(text(BACKFILL_QUERY)).fetchall()
    if not rows:
        return {"eligible": 0, "updated": 0}
    updates = []
    for row in rows:
        mm_id     = row[0]
        parent_cs = float(row[1]) if row[1] is not None else None
        child_cs  = float(row[2]) if row[2] is not None else None
        if child_cs is None:
            continue
        score_delta = (child_cs - parent_cs) if parent_cs is not None else None
        improved    = (score_delta > 0) if score_delta is not None else None
        updates.append({
            "mm_id": str(mm_id),
            "child_cs": child_cs,
            "score_delta": score_delta,
            "improved": improved,
        })
    if not updates:
        return {"eligible": len(rows), "updated": 0}
    with engine.begin() as conn:
        for u in updates:
            conn.execute(text(UPDATE_QUERY), {
                "mm_id": u["mm_id"],
                "child_cs": u["child_cs"],
                "score_delta": u["score_delta"],
                "improved": u["improved"],
            })
    return {"eligible": len(rows), "updated": len(updates)}


def print_leaderboard(engine) -> None:
    query = """
        SELECT
            mutation_type,
            COUNT(*)                                                                    AS total,
            COUNT(*) FILTER (WHERE improved = TRUE)                                     AS ok,
            COUNT(*) FILTER (WHERE improved = FALSE)                                    AS fail,
            COUNT(*) FILTER (WHERE improved IS NULL)                                    AS pend,
            ROUND(AVG(score_delta)::numeric, 2)                                         AS avg_d,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE improved = TRUE)
                / NULLIF(COUNT(*) FILTER (WHERE improved IS NOT NULL), 0), 1
            )                                                                           AS conv
        FROM mutation_memory
        GROUP BY mutation_type
        ORDER BY conv DESC NULLS LAST, avg_d DESC NULLS LAST
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    print("\n" + "=" * 90)
    print("  ATLAS MUTATION LEADERBOARD — Day 8.6 Activated")
    print("=" * 90)
    print(f"  {'MUTATION TYPE':<44} {'TOT':>4} {'CONV%':>7} {'AVG_D':>8} {'OK':>5} {'FAIL':>5} {'PEND':>5}")
    print("-" * 90)
    for r in rows:
        conv  = f"{float(r[6]):.1f}%" if r[6] is not None else "  N/A"
        delta = f"{float(r[5]):+.2f}" if r[5] is not None else "  N/A"
        print(f"  {r[0]:<44} {r[1]:>4} {conv:>7} {delta:>8} {r[2]:>5} {r[3]:>5} {r[4]:>5}")
    print("=" * 90 + "\n")


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    runner = BacktestRunner(redis_client)
    await runner.timescale.connect()

    # 1. Find pending children
    children = await get_pending_children(db)
    logger.info(f"Found {len(children)} pending mutation children to process")

    if not children:
        logger.info("All mutation children already scored. Running backfill check...")
    else:
        success, failed = 0, 0
        for i, child in enumerate(children):
            sid  = child["id"]
            name = child.get("name", "?")
            status = child.get("status", "?")
            print(f"  [{i+1}/{len(children)}] {name} ({status})", end=" ", flush=True)
            try:
                if child.get("status") == "pending_code":
                    from atlas.agents.l2_strategy.coder_agent import CoderAgent
                    coder = CoderAgent(redis_client, db)
                    await coder._code_strategy(child)
                    
                    # Refetch to get the updated code and status
                    query = f"SELECT code, status FROM strategies WHERE id = '{sid}'"
                    async with db.engine.connect() as conn:
                        res = await conn.execute(text(query))
                        row = res.fetchone()
                        if row:
                            child["code"] = row.code
                            child["status"] = row.status

                if child.get("status") != "pending_backtest":
                    print(f"Skipped (status={child.get('status')})")
                    continue
                    
                await runner.process_strategy(child)
                print("OK")
                success += 1
            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1

        print(f"\n  Backtest complete: {success} OK, {failed} FAILED")

    # 2. Backfill composite scores into mutation_memory
    from sqlalchemy import create_engine as sync_engine
    sync_db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    sync_eng = sync_engine(sync_db_url)

    result = run_backfill_sync(sync_eng)
    logger.info(f"Backfill: {result['updated']} rows updated out of {result['eligible']} eligible")

    # 3. Print live leaderboard
    if result["updated"] > 0 or not children:
        print_leaderboard(sync_eng)
    else:
        logger.warning("No new scores populated. Check if children were successfully backtested.")

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
