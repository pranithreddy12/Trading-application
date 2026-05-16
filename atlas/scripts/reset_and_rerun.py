import asyncio
from loguru import logger
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent


async def main():
    db = TimescaleClient("postgresql+asyncpg://postgres:password@localhost:5433/atlas")
    await db.connect()

    # Step 1: Reset all strategies to pending_backtest
    async with db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM backtest_results"))
        await conn.execute(text("DELETE FROM strategies"))
        await conn.execute(text("DELETE FROM system_logs"))
    logger.info("Cleared strategies, backtest_results, and system_logs")

    # Step 3: Re-run BacktestRunner on all
    from redis.asyncio import Redis
    from atlas.config.settings import settings

    redis_client = Redis.from_url(settings.redis_url)
    runner = BacktestRunner(redis_client)

    pending = await db.get_strategies_by_status("pending_backtest")
    logger.info(f"Re-running backtests on {len(pending)} strategies")

    for s in pending:
        try:
            await runner._run_for_strategy(s)
        except Exception as e:
            logger.error(f"Backtest error for {s.get('name')}: {e}")

    # Step 4: Run validator
    validator = ValidatorAgent(db_client=db)
    to_validate = await db.get_strategies_by_status("pending_validation")
    logger.info(f"Validating {len(to_validate)} strategies")

    for s in to_validate:
        await validator._validate_one(s["id"], s.get("name", "unknown"))

    # Final report
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT status, COUNT(*)
                FROM strategies
                GROUP BY status
                ORDER BY count DESC
            """)
        )
        rows = result.fetchall()

    logger.info("=" * 50)
    logger.info("PIPELINE RESET COMPLETE")
    for r in rows:
        logger.info(f"  {r[0]}: {r[1]}")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
