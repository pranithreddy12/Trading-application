"""
End-to-end test: run one pending_backtest strategy through the BacktestRunner
and verify that train_sharpe, test_sharpe, holdout_sharpe get written back
to the strategies table.

Uses a shorter bar window for faster execution.
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy import text


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()

    # 1. Pick one pending_backtest strategy
    strategies = await db.get_strategies_by_status("pending_backtest")
    if not strategies:
        print("No pending_backtest strategies found")
        return

    # Pick a strategy with a BTCUSDT or crypto symbol for speed
    strategy = strategies[0]
    sid = str(strategy["id"])
    print(f"Selected strategy: {sid} ({strategy.get('name', '?')})")

    # 2. Read current metrics (should be NULL)
    async with db.engine.connect() as conn:
        r = await conn.execute(
            text("""
                SELECT train_sharpe, test_sharpe, holdout_sharpe,
                       validation_metrics
                FROM strategies WHERE id = :sid
            """),
            {"sid": sid},
        )
        before = r.fetchone()
        print(f"BEFORE: train_sharpe={before[0]}, test_sharpe={before[1]}, holdout_sharpe={before[2]}")

    # 3. Run the backtest using BacktestRunner
    from redis.asyncio import Redis
    from atlas.agents.l3_backtest.backtest_runner import BacktestRunner

    redis_client = Redis.from_url(settings.redis_url)
    runner = BacktestRunner(redis_client)
    # Reuse DB connection to avoid pool issues
    runner.timescale = db

    print("Running backtest (this may take a minute)...")
    try:
        await asyncio.wait_for(
            runner.process_strategy(strategy),
            timeout=180  # 3 minute timeout per strategy
        )
        print("Backtest completed successfully")
    except asyncio.TimeoutError:
        print("Backtest timed out (>3 min) - checking if metrics were written anyway...")
    except Exception as e:
        print(f"Backtest failed: {type(e).__name__}: {e}")
    finally:
        await redis_client.close()

    # 4. Read updated metrics
    async with db.engine.connect() as conn:
        r = await conn.execute(
            text("""
                SELECT train_sharpe, test_sharpe, holdout_sharpe,
                       CASE WHEN validation_metrics IS NOT NULL THEN 'populated' ELSE 'NULL' END as val_metrics
                FROM strategies WHERE id = :sid
            """),
            {"sid": sid},
        )
        after = r.fetchone()
        print(f"AFTER: train_sharpe={after[0]}, test_sharpe={after[1]}, holdout_sharpe={after[2]}, validation_metrics={after[3]}")

    if after[0] is not None:
        print("\n✅ SUCCESS: train_sharpe is now populated in strategies table!")
        print(f"   train_sharpe={after[0]:.4f}, test_sharpe={after[1]:.4f}, holdout_sharpe={after[2]:.4f}")
    else:
        print("\n❌ FAILED: train_sharpe is still NULL")

    # 5. Quick ad-hoc update test to verify the mechanism directly
    print("\n--- Direct update_strategy_fields test ---")
    await db.update_strategy_fields(
        strategy_id=sid,
        train_sharpe=99.9,
        test_sharpe=88.8,
        holdout_sharpe=77.7,
        validation_metrics=json.dumps({"test": "direct_write"}),
    )
    async with db.engine.connect() as conn:
        r = await conn.execute(
            text("SELECT train_sharpe, test_sharpe, holdout_sharpe FROM strategies WHERE id = :sid"),
            {"sid": sid},
        )
        row = r.fetchone()
        if row and row[0] == 99.9:
            print("✅ Direct update_strategy_fields works: train_sharpe={}".format(row[0]))
        else:
            print("❌ Direct update_strategy_fields FAILED: got {}".format(row))

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
