"""
End-to-end pipeline runner: Ideator → Coder → Backtest → Validator → Mutator → Combiner.
Clears DB, generates N strategies, processes through full pipeline, reports results.
"""

import asyncio
import time
from loguru import logger
from sqlalchemy import text
from redis.asyncio import Redis

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.ideator_agent import IdeatorAgent
from atlas.agents.l2_strategy.coder_agent import CoderAgent
from atlas.agents.l2_strategy.mutator_agent import MutatorAgent
from atlas.agents.l2_strategy.combiner_agent import CombinerAgent
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent

TARGET_STRATEGIES = 10
TOTAL_TIMEOUT = 600  # 10 min max


async def wait_for_strategies(db, target_count, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        rows = await db.get_strategies_by_status("pending_code")
        if len(rows) >= target_count:
            return rows
        await asyncio.sleep(5)
    return await db.get_strategies_by_status("pending_code")


async def run_ideators(db, redis_client):
    agents = [
        IdeatorAgent(i, [0.3, 0.5, 0.7, 0.9, 1.0][i], redis_client, db)
        for i in range(5)
    ]
    tasks = [a.start() for a in agents]
    done, pending = await asyncio.wait(
        [asyncio.create_task(t) for t in tasks],
        timeout=120,  # run for 2 min
    )
    for a in agents:
        await a.stop()
    return agents


async def run_coder(db, redis_client):
    agent = CoderAgent(redis_client, db)
    strategies = await db.get_strategies_by_status("pending_code")
    logger.info(f"Coder: processing {len(strategies)} strategies")
    for s in strategies:
        await agent._code_strategy(s)


async def run_backtest(db, redis_client):
    runner = BacktestRunner(redis_client)
    strategies = await db.get_strategies_by_status("pending_backtest")
    logger.info(f"Backtest: processing {len(strategies)} strategies")
    for s in strategies:
        await runner.process_strategy(s)


async def run_validator(db):
    agent = ValidatorAgent(db)
    strategies = await db.get_strategies_by_status("pending_validation")
    logger.info(f"Validator: processing {len(strategies)} strategies")
    for s in strategies:
        await agent._validate_one(s["id"], s.get("name", "unknown"))


async def report(db):
    print("\n" + "=" * 70)
    print("PIPELINE RESULTS")
    print("=" * 70)
    async with db.engine.connect() as conn:
        rows = (
            await conn.execute(
                text("""
            SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC
        """)
            )
        ).fetchall()
        print(f"{'Status':<25} {'Count':<10}")
        print("-" * 35)
        for r in rows:
            print(f"{r[0]:<25} {r[1]:<10}")

        print("\n--- Validated Strategy Details ---")
        rows2 = (
            await conn.execute(
                text("""
            SELECT s.name, b.sharpe, b.total_trades, b.win_rate, b.max_drawdown
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE s.status IN ('validated_A', 'validated_B')
            ORDER BY b.sharpe DESC
        """)
            )
        ).fetchall()
        if rows2:
            print(
                f"{'Name':<45} {'Sharpe':<10} {'Trades':<8} {'WinRate':<10} {'Drawdown':<10}"
            )
            print("-" * 83)
            for r in rows2:
                print(
                    f"{str(r[0])[:42]:<45} {float(r[1]):<10.2f} {int(r[2]):<8} {float(r[3]):<10.3f} {float(r[4]):<10.2f}"
                )
        else:
            print("No validated_A/B strategies")

        print("\n--- Failed Validation (last 5) ---")
        rows3 = (
            await conn.execute(
                text("""
            SELECT name FROM strategies WHERE status = 'failed_validation' ORDER BY created_at DESC LIMIT 5
        """)
            )
        ).fetchall()
        for r in rows3:
            print(f"  {r[0]}")

        print("\n--- Code Failed (count) ---")
        cf = (
            await conn.execute(
                text("SELECT COUNT(*) FROM strategies WHERE status = 'code_failed'")
            )
        ).scalar()
        print(f"  code_failed: {cf}")

        print("\n--- Backtest Results Summary ---")
        rows4 = (
            await conn.execute(
                text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE total_trades >= 5) as with_enough_trades,
                COUNT(*) FILTER (WHERE total_trades = 0) as zero_trades,
                ROUND(AVG(sharpe)::numeric, 2) as avg_sharpe,
                ROUND(AVG(total_trades)::numeric, 1) as avg_trades
            FROM backtest_results
        """)
            )
        ).fetchall()
        if rows4:
            r = rows4[0]
            print(f"  Total backtests:       {r[0]}")
            print(f"  With >=5 trades:       {r[1]}")
            print(f"  With 0 trades:         {r[2]}")
            print(f"  Average Sharpe:        {r[3]}")
            print(f"  Average trades:        {r[4]}")
    print("=" * 70)


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    # Clear
    async with db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM backtest_results"))
        await conn.execute(text("DELETE FROM strategies"))
        await conn.execute(text("DELETE FROM system_logs"))
    logger.info("DB cleared")

    # Phase 1: Generate strategies via Ideator
    logger.info("=" * 50)
    logger.info("PHASE 1: Ideator - generating strategies via Claude")
    logger.info("=" * 50)
    agents = [
        IdeatorAgent(i, [0.3, 0.5, 0.7, 0.9, 1.0][i], redis_client, db)
        for i in range(5)
    ]
    ideator_tasks = [asyncio.create_task(a.start()) for a in agents]

    # Wait for enough strategies
    logger.info(f"Waiting for {TARGET_STRATEGIES}+ strategies...")
    count = 0
    start_time = time.time()
    while count < TARGET_STRATEGIES and time.time() - start_time < 180:
        await asyncio.sleep(5)
        rows = await db.get_strategies_by_status("pending_code")
        count = len(rows)
        logger.info(f"  Strategies generated so far: {count}")

    # Stop ideators
    for a in agents:
        await a.stop()
    for t in ideator_tasks:
        t.cancel()
    logger.info(f"Ideator complete: {count} strategies generated")

    if count == 0:
        logger.error("No strategies generated - aborting")
        return

    # Phase 2: Code generation
    logger.info("=" * 50)
    logger.info("PHASE 2: Coder - generating code from strategy specs")
    logger.info("=" * 50)
    coder = CoderAgent(redis_client, db)
    pending = await db.get_strategies_by_status("pending_code")
    logger.info(f"Found {len(pending)} strategies to code")
    for s in pending:
        await coder._code_strategy(s)

    # Phase 3: Backtest
    logger.info("=" * 50)
    logger.info("PHASE 3: BacktestRunner - running backtests")
    logger.info("=" * 50)
    runner = BacktestRunner(redis_client)
    pending = await db.get_strategies_by_status("pending_backtest")
    logger.info(f"Found {len(pending)} strategies to backtest")
    for s in pending:
        await runner.process_strategy(s)

    # Phase 4: Validate
    logger.info("=" * 50)
    logger.info("PHASE 4: ValidatorAgent - validating results")
    logger.info("=" * 50)
    validator = ValidatorAgent(db)
    pending = await db.get_strategies_by_status("pending_validation")
    logger.info(f"Found {len(pending)} strategies to validate")
    for s in pending:
        await validator._validate_one(s["id"], s.get("name", "unknown"))

    # Phase 5: Mutator - refine weak-but-viable strategies
    logger.info("=" * 50)
    logger.info("PHASE 5: MutatorAgent - refining borderline strategies")
    logger.info("=" * 50)
    mutator = MutatorAgent(redis_client, db)
    await mutator._mutation_cycle()

    # Phase 6: Combiner - hybridize top strategies
    logger.info("=" * 50)
    logger.info("PHASE 6: CombinerAgent - hybridizing top strategies")
    logger.info("=" * 50)
    combiner = CombinerAgent(redis_client, db)
    await combiner._combine_top_strategies()

    # Report
    await report(db)
    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
