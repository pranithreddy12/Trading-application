import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy.sql import text

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT status, COUNT(*) FROM strategies GROUP BY status"))
        print("Strategy Status Distribution:")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
        r = await conn.execute(text("SELECT symbol, side, qty, strategy_id FROM positions"))
        print("\nOpen Positions:")
        for row in r.fetchall():
            print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
