
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text

async def check():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            r = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'paper_trades'"))
            cols = [row[0] for row in r.fetchall()]
            print(f"Paper Trades Columns: {cols}")
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(check())
