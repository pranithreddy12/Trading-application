import asyncio
import json
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner


async def main(name: str):
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    timescale = TimescaleClient(settings.database_url)
    await timescale.connect()

    async with timescale.engine.connect() as conn:
        r = await conn.execute(
            text("""
            SELECT * FROM strategies WHERE name = :name LIMIT 1
            """),
            {"name": name},
        )
        row = r.fetchone()
        if not row:
            print(f"Strategy not found: {name}")
            return
        # Convert to dict
        strategy = dict(row._mapping)
        # Ensure parameters parsed
        if isinstance(strategy.get('parameters'), str):
            try:
                strategy['parameters'] = json.loads(strategy['parameters'])
            except Exception:
                pass

    runner = BacktestRunner(redis_client)
    # connect internal timescale client used by runner
    await runner.timescale.connect()

    print(f"Running backtest for strategy {name} ({strategy.get('id')})")
    await runner.process_strategy(strategy)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python scripts/tools/run_single_backtest.py <strategy_name>')
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
