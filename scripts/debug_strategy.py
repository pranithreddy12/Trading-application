import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy.sql import text

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        sid = '0dffeed2-dd8c-431e-9401-b0d9d8dc46a1'
        r = await conn.execute(text("SELECT id, status FROM strategies WHERE id::text = :id"), {"id": sid})
        print(f"Strategy: {r.fetchone()}")
        
        r = await conn.execute(text("SELECT COUNT(*) FROM backtest_results WHERE strategy_id::text = :id"), {"id": sid})
        print(f"Backtest Count: {r.scalar()}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
