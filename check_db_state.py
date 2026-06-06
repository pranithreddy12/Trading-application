
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text

async def check():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            # Check market_data_l1
            r = await conn.execute(text('SELECT symbol, close, time FROM market_data_l1 ORDER BY time DESC LIMIT 5'))
            print("Latest Market Data L1:")
            for row in r.fetchall():
                print(row)
            
            # Check positions
            # Let's check the actual columns first
            r = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'positions'"))
            cols = [row[0] for row in r.fetchall()]
            print(f"\nPositions Table Columns: {cols}")

            r = await conn.execute(text('SELECT * FROM positions LIMIT 5'))
            print("\nPositions Content:")
            for row in r.fetchall():
                print(row)
                
            # Check paper_trades
            r = await conn.execute(text('SELECT * FROM paper_trades WHERE pnl <> 0 LIMIT 5'))
            print("\nPaper Trades (pnl <> 0):")
            for row in r.fetchall():
                print(row)
                
            r = await conn.execute(text('SELECT COUNT(*) FROM paper_trades'))
            print(f"\nTotal Paper Trades: {r.scalar()}")
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(check())
