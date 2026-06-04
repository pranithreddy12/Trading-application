import asyncio
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy import text

async def main():
    db = TimescaleClient(get_settings().database_url)
    await db.connect(run_migrations=False)
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT status, COUNT(*) FROM strategies GROUP BY status"))
        print("\n--- Strategy Counts by Status ---")
        for row in res.fetchall():
            print(f"  {row[0]}: {row[1]}")
    await db.close()

if __name__ == '__main__':
    asyncio.run(main())
