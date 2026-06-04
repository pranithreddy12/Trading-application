
import asyncio
from atlas.agents.l1_data.polygon_rest_agent import PolygonRestAgent
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
import redis.asyncio as redis
from sqlalchemy import text

async def run_polygon_and_check():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    r_client = redis.from_url(settings.redis_url)
    
    # Force a higher rate limit for the test if possible, or just wait
    agent = PolygonRestAgent(r_client, settings.database_url)
    
    print("Starting Polygon Ingestion Agent for 2 minutes...")
    agent_task = asyncio.create_task(agent.run())
    
    # 1. Initial check
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'polygon'"))
        start_time = r.scalar()
        print(f"Initial Polygon Last Tick: {start_time}")

    print("Waiting 130 seconds...")
    await asyncio.sleep(130)
    
    # 2. Final check
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'polygon'"))
        end_time = r.scalar()
        print(f"Final Polygon Last Tick:   {end_time}")
        
    await agent.stop()
    agent_task.cancel()
    
    if end_time and (start_time is None or end_time > start_time):
        print("\nPOLYGON LEVEL 3 VERIFIED: Equity data is flowing.")
    else:
        print("\nPOLYGON LEVEL 3 FAILED: No new equity data. Markets may be closed or API limited.")

if __name__ == '__main__':
    asyncio.run(run_polygon_and_check())
