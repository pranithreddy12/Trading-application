
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def check_data_ranges():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        print("--- Date Ranges for Backtest Data ---")
        
        # market_data_l1
        try:
            r = await conn.execute(text("SELECT MIN(time), MAX(time) FROM market_data_l1"))
            min_time, max_time = r.fetchone()
            print(f"market_data_l1: {min_time} TO {max_time}")
        except Exception as e:
            print(f"market_data_l1: Error - {e}")

        # features
        try:
            r = await conn.execute(text("SELECT MIN(time), MAX(time) FROM features"))
            min_time, max_time = r.fetchone()
            print(f"features:       {min_time} TO {max_time}")
        except Exception as e:
            print(f"features: Error - {e}")
            
        # features_wide
        try:
            r = await conn.execute(text("SELECT MIN(time), MAX(time) FROM features_wide"))
            min_time, max_time = r.fetchone()
            print(f"features_wide:  {min_time} TO {max_time}")
        except Exception as e:
            print(f"features_wide: Error - {e}")

if __name__ == '__main__':
    asyncio.run(check_data_ranges())
