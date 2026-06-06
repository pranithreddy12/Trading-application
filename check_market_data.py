
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text

async def check():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            for sym in ['AMD', 'TSLA', 'SOLUSDT']:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM market_data_l1 WHERE symbol = '{sym}'"))
                print(f"{sym} count: {r.scalar()}")
                r = await conn.execute(text(f"SELECT close, time FROM market_data_l1 WHERE symbol = '{sym}' ORDER BY time DESC LIMIT 1"))
                print(f"Latest {sym}: {r.fetchone()}")
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(check())
