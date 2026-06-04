
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def check_trade_count():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
        count = r.scalar()
        print(f"Current paper_trades count: {count}")
        
        r2 = await conn.execute(text("SELECT COUNT(*) FROM positions"))
        count_pos = r2.scalar()
        print(f"Current open positions count: {count_pos}")

if __name__ == '__main__':
    asyncio.run(check_trade_count())
