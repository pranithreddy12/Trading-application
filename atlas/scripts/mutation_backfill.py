"""
mutation_backfill.py — Day 8.6 Child Score Activation.

Purpose:
  Joins mutation_memory child_strategy_id → backtest_results → composite_score,
  then UPDATEs mutation_memory with:
    - child_composite_score
    - score_delta  (child - parent)
    - improved     (score_delta > 0)

Design:
  - Restart-safe: only processes rows where child_composite_score IS NULL
  - Idempotent: safe to run multiple times — skips already-filled rows
  - Only updates rows where the child has a backtest result with a composite_score
  - Children still in pending_backtest / pending_code are skipped (deferred lifecycle)

Usage:
  python scripts/mutation_backfill.py
  python -m scripts.mutation_backfill
"""

import asyncio
from loguru import logger
from sqlalchemy import create_engine, text
from atlas.config.settings import get_settings


BACKFILL_QUERY = """
    SELECT
        mm.id                               AS mm_id,
        mm.parent_composite_score           AS parent_cs,
        (b.results->>'composite_score')::NUMERIC AS child_cs
    FROM mutation_memory mm
    JOIN strategies s ON mm.child_strategy_id = s.id
    JOIN backtest_results b ON s.id = b.strategy_id
    WHERE
        mm.child_composite_score IS NULL
        AND b.results ? 'composite_score'
        AND (b.results->>'composite_score')::TEXT <> 'null'
"""

UPDATE_QUERY = """
    UPDATE mutation_memory
    SET
        child_composite_score = :child_cs,
        score_delta           = :score_delta,
        improved              = :improved
    WHERE id = :mm_id
"""


def run_backfill(engine) -> dict:
    """
    Execute the backfill. Returns a summary dict with counts.
    Idempotent — only processes rows where child_composite_score IS NULL.
    """
    with engine.begin() as conn:
        rows = conn.execute(text(BACKFILL_QUERY)).fetchall()

    if not rows:
        return {"eligible": 0, "updated": 0, "skipped_no_parent": 0}

    updates = []
    skipped_no_parent = 0

    for row in rows:
        mm_id    = row[0]
        parent_cs = float(row[1]) if row[1] is not None else None
        child_cs  = float(row[2]) if row[2] is not None else None

        if child_cs is None:
            continue

        if parent_cs is not None:
            score_delta = child_cs - parent_cs
            improved    = score_delta > 0
        else:
            # Parent score was not captured at mutation time (pre-Day-8.5 records)
            score_delta = None
            improved    = None
            skipped_no_parent += 1

        updates.append({
            "mm_id":      str(mm_id),
            "child_cs":   child_cs,
            "score_delta": score_delta,
            "improved":    improved,
        })

    if not updates:
        return {"eligible": len(rows), "updated": 0, "skipped_no_parent": skipped_no_parent}

    with engine.begin() as conn:
        for u in updates:
            conn.execute(text(UPDATE_QUERY), {
                "mm_id":      u["mm_id"],
                "child_cs":   u["child_cs"],
                "score_delta": u["score_delta"],
                "improved":    u["improved"],
            })

    return {
        "eligible":           len(rows),
        "updated":            len(updates),
        "skipped_no_parent":  skipped_no_parent,
    }


def print_summary(engine) -> None:
    """Print a post-backfill snapshot of mutation_memory scoring state."""
    query = """
        SELECT
            mutation_type,
            COUNT(*)                                        AS total,
            COUNT(*) FILTER (WHERE improved = TRUE)        AS improved,
            COUNT(*) FILTER (WHERE improved = FALSE)       AS failed,
            COUNT(*) FILTER (WHERE improved IS NULL)       AS pending,
            ROUND(AVG(score_delta)::numeric, 2)            AS avg_delta,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE improved = TRUE)
                / NULLIF(COUNT(*) FILTER (WHERE improved IS NOT NULL), 0),
                1
            )                                              AS conv_pct
        FROM mutation_memory
        GROUP BY mutation_type
        ORDER BY conv_pct DESC NULLS LAST, avg_delta DESC NULLS LAST
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    print("\n" + "=" * 85)
    print("  MUTATION LEADERBOARD (POST-BACKFILL)")
    print("=" * 85)
    print(f"  {'MUTATION TYPE':<42} {'TOTAL':>5} {'CONV%':>6} {'AVG D':>8} {'OK':>5} {'FAIL':>5} {'PEND':>5}")
    print("-" * 85)
    for r in rows:
        conv  = f"{r[6]:.1f}%" if r[6] is not None else "  N/A"
        delta = f"{r[5]:+.2f}"  if r[5] is not None else "  N/A"
        print(f"  {r[0]:<42} {r[1]:>5} {conv:>6} {delta:>8} {r[2]:>5} {r[3]:>5} {r[4]:>5}")
    print("=" * 85 + "\n")


async def main():
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)

    logger.info("=== mutation_backfill.py — Day 8.6 Child Score Activation ===")

    result = run_backfill(engine)

    logger.info(f"Eligible rows (child has backtest score): {result['eligible']}")
    logger.info(f"Updated rows                             : {result['updated']}")
    logger.info(f"Skipped (no parent_composite_score)      : {result['skipped_no_parent']}")

    if result["updated"] > 0:
        logger.info("Backfill complete — printing leaderboard.")
        print_summary(engine)
    elif result["eligible"] == 0:
        logger.info("No eligible rows found. Either all scores are filled or children not yet backtested.")
    else:
        logger.warning("Eligible rows found but 0 updated — check child_cs extraction.")


if __name__ == "__main__":
    asyncio.run(main())
