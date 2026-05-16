"""
Batch re-run all failed_validation strategies through backtest + validation.
Resets them to pending_backtest, processes in batches, and reports.
"""

import asyncio
import time
from loguru import logger
from sqlalchemy import text
from redis.asyncio import Redis
import sys

sys.path.insert(0, ".")
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent

BATCH_SIZE = 100
SLEEP_BETWEEN_BATCHES = 2


async def reset_all(db):
    """Reset all strategies to pending_backtest where appropriate."""
    async with db.engine.begin() as conn:
        # failed_validation -> pending_backtest
        r1 = await conn.execute(
            text("""
            UPDATE strategies SET status = 'pending_backtest'
            WHERE status = 'failed_validation'
        """)
        )
        print(f"  Reset {r1.rowcount} failed_validation -> pending_backtest")

        # Delete stale backtest_results for these
        await conn.execute(
            text("""
            DELETE FROM backtest_results b
            WHERE b.strategy_id IN (
                SELECT id FROM strategies WHERE status = 'pending_backtest'
            )
        """)
        )

    rows = await db.get_strategies_by_status("pending_backtest")
    print(f"  Total pending_backtest: {len(rows)}")
    return rows


async def run_backtests_batch(db, redis_client, strategies, batch_num=1):
    """Run backtests on a batch of strategies."""
    runner = BacktestRunner(redis_client)
    count = 0
    start = time.time()

    for s in strategies:
        try:
            await runner.process_strategy(s)
            count += 1
        except Exception as e:
            logger.error(f"Error processing {s.get('name', '?')}: {e}")
        await asyncio.sleep(0.3)

    elapsed = time.time() - start
    print(
        f"  Batch {batch_num}: {count} strategies in {elapsed:.1f}s ({elapsed / max(count, 1):.1f}s each)"
    )
    return count


async def run_validator_all(db):
    """Validate all pending_validation strategies."""
    validator = ValidatorAgent(db)
    strategies = await db.get_strategies_by_status("pending_validation")
    total = len(strategies)
    print(f"\n  Validator: processing {total} strategies")

    count = 0
    for s in strategies:
        try:
            await validator._validate_one(s["id"], s.get("name", "unknown"))
            count += 1
        except Exception as e:
            logger.error(f"Validation error for {s.get('name', '?')}: {e}")

    print(f"  Validated: {count}")
    return count


async def report(db):
    """Final report."""
    async with db.engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC"
                )
            )
        ).fetchall()
        print("\n" + "=" * 60)
        print("BATCH RE-RUN COMPLETE")
        print("=" * 60)
        print(f"{'Status':<25} {'Count':<10}")
        print("-" * 35)
        for r in rows:
            print(f"{r[0]:<25} {r[1]:<10}")

        rows2 = (
            await conn.execute(
                text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE entry_count > 0) as with_entries,
                COUNT(*) FILTER (WHERE entry_count = 0) as zero_entries,
                ROUND(AVG(entry_count)::numeric, 1) as avg_entry,
                ROUND(AVG(total_trades)::numeric, 1) as avg_trades,
                ROUND(AVG(sharpe)::numeric, 2) as avg_sharpe
            FROM backtest_results
        """)
            )
        ).fetchall()
        r = rows2[0]
        print(f"\n  Total backtested:           {r[0]}")
        print(f"  With entry_count > 0:       {r[1]}")
        print(f"  With entry_count = 0:       {r[2]}")
        print(f"  Average entry_count:        {r[3]}")
        print(f"  Average trades:             {r[4]}")
        print(f"  Average Sharpe:             {r[5]}")

        # Validated strategies
        rows3 = (
            await conn.execute(
                text("""
            SELECT s.status, s.name, b.sharpe, b.total_trades, b.entry_count
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE s.status IN ('validated_A', 'validated_B', 'research_candidate')
            ORDER BY b.sharpe DESC
            LIMIT 20
        """)
            )
        ).fetchall()
        if rows3:
            print(f"\n  --- Validated/Research Strategies ---")
            print(
                f"  {'Status':<20} {'Name':<45} {'Sharpe':<8} {'Trades':<8} {'Entries':<8}"
            )
            print(f"  {'-' * 18} {'-' * 43} {'-' * 6} {'-' * 6} {'-' * 6}")
            for r in rows3:
                print(
                    f"  {r[0]:<20} {str(r[1])[:42]:<45} {float(r[2]):<8.2f} {int(r[3]):<8} {int(r[4]):<8}"
                )

    print("=" * 60)


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    print("=" * 60)
    print("BATCH RE-RUN: Resetting + Backtesting + Validating")
    print("=" * 60)

    print("\nSTEP 1: Reset all failed_validation -> pending_backtest")
    strategies = await reset_all(db)

    if not strategies:
        print("No strategies to re-run")
        return

    print(
        f"\nSTEP 2: Backtesting {len(strategies)} strategies in batches of {BATCH_SIZE}"
    )
    total_backtested = 0
    for i in range(0, len(strategies), BATCH_SIZE):
        batch = strategies[i : i + BATCH_SIZE]
        count = await run_backtests_batch(db, redis_client, batch, i // BATCH_SIZE + 1)
        total_backtested += count
        await asyncio.sleep(SLEEP_BETWEEN_BATCHES)
    print(f"\n  Total backtested: {total_backtested}")

    print(f"\nSTEP 3: Running ValidatorAgent on all pending_validation")
    validated_count = await run_validator_all(db)
    print(f"  Total validated: {validated_count}")

    print(f"\nSTEP 4: Final Report")
    await report(db)

    await redis_client.aclose()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
