import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy.sql import text

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT id, strategy_id, symbol, side, qty, time FROM paper_trades ORDER BY time DESC LIMIT 20"))
        print("Recent Paper Trades:")
        for row in r.fetchall():
            print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
