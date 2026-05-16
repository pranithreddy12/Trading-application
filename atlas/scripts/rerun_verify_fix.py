"""
Verify the feature persistence fix by re-running strategies through backtest + validation.
Resets a sample set, processes them, and reports entry_count > 0 as the truth test.
"""

import asyncio
import json
import sys
from loguru import logger
from sqlalchemy import text
from redis.asyncio import Redis

sys.path.insert(0, ".")
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent

SAMPLE_SIZE = 50  # Process this many from failed_validation + control strategies


async def reset_strategies(db):
    """Reset control strategies + a sample of failed_validation to pending_backtest."""
    async with db.engine.begin() as conn:
        # Reset control strategies
        result = await conn.execute(
            text("""
                UPDATE strategies 
                SET status = 'pending_backtest' 
                WHERE name ILIKE '%control%'
            """)
        )
        print(f"  Reset {result.rowcount} control strategies")

        # Delete old backtest_results for control strategies
        await conn.execute(
            text("""
                DELETE FROM backtest_results b
                USING strategies s
                WHERE b.strategy_id = s.id AND s.name ILIKE '%control%'
            """)
        )

        # Reset a sample of failed_validation
        result = await conn.execute(
            text(f"""
                UPDATE strategies 
                SET status = 'pending_backtest' 
                WHERE id IN (
                    SELECT id FROM strategies 
                    WHERE status = 'failed_validation' 
                    LIMIT {SAMPLE_SIZE}
                )
            """)
        )
        print(f"  Reset {result.rowcount} failed_validation -> pending_backtest")

        # Delete old backtest_results for the sample
        await conn.execute(
            text(f"""
                DELETE FROM backtest_results b
                WHERE b.strategy_id IN (
                    SELECT id FROM strategies 
                    WHERE status = 'pending_backtest'
                )
            """)
        )

    # Count what's pending
    rows = await db.get_strategies_by_status("pending_backtest")
    print(f"  Total pending_backtest now: {len(rows)}")
    return rows


async def run_backtests(db, redis_client, strategies):
    """Run backtests on a list of strategies."""
    runner = BacktestRunner(redis_client)
    success_count = 0
    zero_entry_count = 0

    for s in strategies:
        try:
            # Save code if not present (for control strategies)
            if not s.get("code") or not s["code"].strip():
                code = _generate_control_code()
                await db.update_strategy_code(
                    s["id"], code, s.get("status", "pending_backtest")
                )
                s["code"] = code

            await runner.process_strategy(s)
            success_count += 1
        except Exception as e:
            logger.error(f"Error processing {s.get('name', '?')}: {e}")

        await asyncio.sleep(0.5)

    return success_count


async def run_validator(db):
    """Validate all pending_validation strategies."""
    validator = ValidatorAgent(db)
    strategies = await db.get_strategies_by_status("pending_validation")
    print(f"\n  Validator: processing {len(strategies)} strategies")

    for s in strategies:
        try:
            await validator._validate_one(s["id"], s.get("name", "unknown"))
        except Exception as e:
            logger.error(f"Validation error for {s.get('name', '?')}: {e}")
        await asyncio.sleep(0.1)

    return len(strategies)


async def report(db):
    """Report results with entry_count focus."""
    async with db.engine.connect() as conn:
        # Overall status
        rows = (
            await conn.execute(
                text(
                    "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC"
                )
            )
        ).fetchall()
        print("\n" + "=" * 60)
        print("PIPELINE RESULTS AFTER FIX VERIFICATION")
        print("=" * 60)
        print(f"{'Status':<25} {'Count':<10}")
        print("-" * 35)
        for r in rows:
            print(f"{r[0]:<25} {r[1]:<10}")

        # Entry count analysis
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
        print(
            f"  With entry_count > 0:      {r[1]}  {'[OK] FIX WORKS' if r[1] > 0 else '[FAIL] STILL BROKEN'}"
        )
        print(f"  With entry_count = 0:      {r[2]}")
        print(f"  Average entry_count:       {r[3]}")
        print(f"  Average trades:            {r[4]}")
        print(f"  Average Sharpe:            {r[5]}")

        # Control strategy results
        rows3 = (
            await conn.execute(
                text("""
            SELECT s.name, b.entry_count, b.total_trades, b.sharpe, s.status
            FROM backtest_results b
            JOIN strategies s ON s.id = b.strategy_id
            WHERE s.name ILIKE '%control%'
        """)
            )
        ).fetchall()

        if rows3:
            print(f"\n  --- Control Strategy Results ---")
            for r in rows3:
                print(
                    f"  {r[0]:40s} entry={r[1]} trades={r[2]} sharpe={r[3]:.2f} status={r[4]}"
                )

        # Top 5 by entry_count
        rows4 = (
            await conn.execute(
                text("""
            SELECT s.name, b.entry_count, b.total_trades, b.sharpe
            FROM backtest_results b
            JOIN strategies s ON s.id = b.strategy_id
            WHERE b.entry_count > 0
            ORDER BY b.entry_count DESC
            LIMIT 5
        """)
            )
        ).fetchall()

        if rows4:
            print(f"\n  --- Top 5 by Entry Count ---")
            for r in rows4:
                print(f"  {r[0]:40s} entry={r[1]} trades={r[2]} sharpe={r[3]:.2f}")

        # Sample with normalized features
        rows5 = (
            await conn.execute(
                text("""
            SELECT s.name, b.entry_count, b.total_trades, b.sharpe
            FROM backtest_results b
            JOIN strategies s ON s.id = b.strategy_id
            WHERE b.entry_count > 0 AND s.name NOT ILIKE '%control%'
            ORDER BY b.sharpe DESC
            LIMIT 5
        """)
            )
        ).fetchall()

        if rows5:
            print(f"\n  --- Best Non-Control by Sharpe (with entries) ---")
            for r in rows5:
                print(f"  {r[0]:40s} entry={r[1]} trades={r[2]} sharpe={r[3]:.2f}")

    print("=" * 60)


def _generate_control_code():
    return """
import pandas as pd
import numpy as np

class ControlRSIReversion:
    def generate_signals(self, df):
        rsi = df.get("rsi_14", pd.Series(50, index=df.index))
        signals = pd.Series(0, index=df.index)
        signals[rsi < 40] = 1
        signals[rsi > 60] = -1
        return signals
"""


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    print("=" * 60)
    print("STEP 1: Reset strategies -> pending_backtest")
    print("=" * 60)
    strategies = await reset_strategies(db)

    print("\n" + "=" * 60)
    print("STEP 2: Run BacktestRunner")
    print("=" * 60)
    count = await run_backtests(db, redis_client, strategies)
    print(f"  Backtests completed: {count}")

    print("\n" + "=" * 60)
    print("STEP 3: Run ValidatorAgent")
    print("=" * 60)
    validated = await run_validator(db)
    print(f"  Validations completed: {validated}")

    print("\n" + "=" * 60)
    print("STEP 4: Final Report")
    print("=" * 60)
    await report(db)

    await redis_client.aclose()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
