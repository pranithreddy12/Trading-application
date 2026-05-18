
import asyncio
from loguru import logger
from redis.asyncio import Redis
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l5_execution.alpaca_executor import AlpacaExecutor
from atlas.config.settings import settings


async def main():
    # Load settings to get DATABASE_URL and REDIS_URL
    db = TimescaleClient(db_url=settings.database_url)
    await db.connect()

    redis = Redis.from_url(settings.redis_url)

    va = await db.get_strategies_by_status("validated_A")
    vb = await db.get_strategies_by_status("validated_B")
    validated = va + vb
    logger.info(
        f"Found {len(validated)} validated strategies (A={len(va)}, B={len(vb)})"
    )

    if not validated:
        logger.error("No validated strategies — run run_validator.py first")
        return

    executor = AlpacaExecutor(db_client=db, redis_client=redis)

    # Execute first 3 equity strategies only
    executed = 0
    for strategy in validated:
        if executed >= 3:
            break
        success = await executor._execute_strategy(strategy)
        if success:
            executed += 1
        await asyncio.sleep(1)

    # Show results
    from sqlalchemy import text

    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("SELECT symbol, side, quantity, fill_price FROM paper_trades")
        )
        trades = result.fetchall()

    logger.info("=" * 50)
    logger.info(f"EXECUTION COMPLETE — {len(trades)} paper trades placed")
    for t in trades:
        logger.info(f"  {t.symbol} {t.side} {t.quantity} @ ${t.fill_price}")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
