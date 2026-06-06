
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text

async def check():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            r = await conn.execute(text('SELECT DISTINCT symbol FROM market_data_l1'))
            print("Symbols in market_data_l1:")
            print([row[0] for row in r.fetchall()])
            
            r = await conn.execute(text('SELECT DISTINCT symbol FROM paper_trades'))
            print("\nSymbols in paper_trades:")
            print([row[0] for row in r.fetchall()])
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(check())
