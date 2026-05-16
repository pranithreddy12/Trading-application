"""
Batch reprocess ALL strategies under short-window metric framework.
1. Clears old backtest_results
2. Resets all non-code-failed strategies to pending_backtest
3. Processes each through updated BacktestRunner (short-window mode)
4. Updates status to pending_validation
"""

import argparse, asyncio, sys, json, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from loguru import logger
from redis.asyncio import Redis

from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    parser = argparse.ArgumentParser(
        description="Batch reprocess strategies under temporal governance"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of strategies to process (dry-run mode)",
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Skip deletion of old backtest_results",
    )
    args = parser.parse_args()

    settings = get_settings()

    db = TimescaleClient(settings.database_url)
    await db.connect()

    redis_client = Redis.from_url(settings.redis_url)

    runner = BacktestRunner(redis_client)
    await runner.timescale.connect()

    # Step 1: Get current state — handle any status that should reprocess
    all_strats = []
    for status in ("pending_validation", "backtest_failed", "pending_backtest"):
        batch = await db.get_strategies_by_status(status)
        all_strats.extend(batch)
    failed_strats = await db.get_strategies_by_status("code_failed")

    # Apply limit for dry-run mode
    if args.limit is not None and args.limit > 0:
        all_strats = all_strats[: args.limit]
        print(f"[DRY-RUN MODE] Limiting to {args.limit} strategies")

    print(
        f"Found {len(all_strats)} reprocessable + {len(failed_strats)} code_failed = {len(all_strats) + len(failed_strats)} total"
    )

    # Step 2: Delete old backtest_results for these strategies
    strat_ids = [s["id"] for s in all_strats]
    if strat_ids and not args.skip_delete:
        placeholders = ",".join([f"'{sid}'" for sid in strat_ids])
        async with db.engine.begin() as conn:
            from sqlalchemy import text

            result = await conn.execute(
                text(
                    f"DELETE FROM backtest_results WHERE strategy_id IN ({placeholders})"
                )
            )
            print(f"Deleted {result.rowcount} old backtest_results rows")
            result = await conn.execute(
                text(
                    f"DELETE FROM backtest_trades WHERE strategy_id IN ({placeholders})"
                )
            )
            print(f"Deleted {result.rowcount} old backtest_trades rows")
    elif strat_ids and args.skip_delete:
        print("Skipping deletion of old backtest_results (--skip-delete)")

    # Step 3: Reset status to pending_backtest
    for s in all_strats:
        await db.update_strategy_status(s["id"], "pending_backtest")
    print(f"Reset {len(all_strats)} strategies to pending_backtest")

    # Step 4: Process each strategy
    pending = await db.get_strategies_by_status("pending_backtest")
    print(f"Processing {len(pending)} strategies through updated backtest runner...")
    print()

    success = 0
    failed = 0
    failure_bucket = {
        "parse": 0,
        "missing_code": 0,
        "missing_features": 0,
        "runtime": 0,
        "other": 0,
    }
    score_changes = []
    for i, s in enumerate(pending):
        sid = s["id"]
        name = s.get("name", "?")
        print(
            f"[{i + 1}/{len(pending)}] Processing {name} ({sid[:8]}...)",
            end=" ",
            flush=True,
        )
        # Capture old short_window_score before deletion
        old_score = None
        try:
            old_result = await db.get_backtest_result(sid)
            if old_result:
                old_score = old_result.get("short_window_score") or old_result.get(
                    "composite_score"
                )
        except Exception:
            pass
        try:
            await runner.process_strategy(s)
            # Capture new score after processing
            new_result = await db.get_backtest_result(sid)
            new_score = None
            if new_result:
                new_score = new_result.get("short_window_score") or new_result.get(
                    "composite_score"
                )
            if old_score is not None or new_score is not None:
                score_changes.append(
                    {
                        "strategy_id": sid,
                        "name": name,
                        "old_score": old_score,
                        "new_score": new_score,
                        "delta": (new_score or 0) - (old_score or 0)
                        if old_score is not None and new_score is not None
                        else None,
                    }
                )
            if new_result:
                print(f"OK (score={new_score})")
            else:
                print("OK")
            success += 1
        except Exception as e:
            err_type = type(e).__name__
            if "parse" in err_type.lower() or "syntax" in str(e).lower():
                failure_bucket["parse"] += 1
            elif "code" in str(e).lower() and "missing" in str(e).lower():
                failure_bucket["missing_code"] += 1
            elif "feature" in str(e).lower():
                failure_bucket["missing_features"] += 1
            elif "runtime" in err_type.lower():
                failure_bucket["runtime"] += 1
            else:
                failure_bucket["other"] += 1
            print(f"ERROR: {err_type}: {e}")
            traceback.print_exc()
            failed += 1

    print()
    print(f"=== BATCH COMPLETE ===")
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {len(failed_strats)} (code_failed)")
    print()
    print("=== FAILURE BUCKET ===")
    for bucket, count in failure_bucket.items():
        if count > 0:
            print(f"  {bucket}: {count}")

    if score_changes:
        print()
        print("=== SCORE CHANGE LOG (first 20) ===")
        for sc in score_changes[:20]:
            delta_str = f"{sc['delta']:+.1f}" if sc["delta"] is not None else "N/A"
            print(
                f"  {sc['name'][:30]:>30} | old={sc['old_score']} new={sc['new_score']} delta={delta_str}"
            )

    # Step 5: Show final state
    print()
    print("=== FINAL STATUS DISTRIBUTION ===")
    async with db.engine.connect() as conn:
        from sqlalchemy import text

        result = await conn.execute(
            text(
                "SELECT status, COUNT(*) as cnt FROM strategies GROUP BY status ORDER BY cnt DESC"
            )
        )
        for row in result:
            print(f"  {row.status:>25}: {row.cnt}")

    print()
    print("=== BACKTEST_RESULTS COUNT ===")
    async with db.engine.connect() as conn:
        cnt = await conn.execute(text("SELECT COUNT(*) FROM backtest_results"))
        print(f"  {cnt.fetchone()[0]} backtest results")

    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
