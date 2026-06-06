import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy.sql import text

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT * FROM paper_trades LIMIT 0"))
        print(f"Paper Trades Columns: {list(r.keys())}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
