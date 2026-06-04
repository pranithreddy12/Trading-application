
import asyncio
import time
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def drift_test():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        print("--- 60-Second Live Drift Test ---")
        
        # 1. Get current state
        r = await conn.execute(text("SELECT symbol, close, time FROM market_data_l1 WHERE source = 'binance' ORDER BY time DESC LIMIT 1"))
        start_tick = r.fetchone()
        if not start_tick:
            print("No Binance data found to test drift.")
            return
        
        print(f"Start Tick: {start_tick[0]} | ${start_tick[1]:<8.2f} | {start_tick[2]}")
        print("Waiting 60 seconds...")
        
        await asyncio.sleep(60)
        
        # 2. Get updated state
        r = await conn.execute(text("SELECT symbol, close, time FROM market_data_l1 WHERE source = 'binance' ORDER BY time DESC LIMIT 1"))
        end_tick = r.fetchone()
        
        print(f"End Tick:   {end_tick[0]} | ${end_tick[1]:<8.2f} | {end_tick[2]}")
        
        if end_tick[2] > start_tick[2]:
            print("\nSUCCESS: Feed is LIVE and actively updating.")
        else:
            print("\nFAILURE: Feed is STALE or replaying historical data.")

if __name__ == '__main__':
    asyncio.run(drift_test())
