import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy.sql import text

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT deployment_mode, COUNT(*) FROM strategies GROUP BY deployment_mode"))
        print("Strategy Deployment Mode Distribution:")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
