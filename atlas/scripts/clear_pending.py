import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy.sql import text

async def clear_old_code():
    s = get_settings()
    db = TimescaleClient(s.database_url)
    await db.connect()
    async with db.engine.begin() as conn:
        res = await conn.execute(text("DELETE FROM strategies WHERE status = 'pending_backtest'"))
        print(f'Deleted {res.rowcount} pending strategies with old buggy code')
    await db.close()

asyncio.run(clear_old_code())
