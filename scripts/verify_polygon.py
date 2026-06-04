
import asyncio
from atlas.agents.l1_data.polygon_rest_agent import PolygonRestAgent
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
import redis.asyncio as redis
from sqlalchemy import text

async def verify_polygon():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    r_client = redis.from_url(settings.redis_url)
    
    agent = PolygonRestAgent(r_client, settings.database_url)
    
    print("Checking Polygon Ingestion...")
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'polygon'"))
        start_time = r.scalar()
        print(f"Initial Polygon Last Tick: {start_time}")

    # Polygon REST agent usually does a backfill or snapshot
    # We'll run it once to see if it updates
    await agent.initialize()
    await agent._run_cycle() # Run one iteration
    
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'polygon'"))
        end_time = r.scalar()
        print(f"Final Polygon Last Tick:   {end_time}")

    if end_time and (start_time is None or end_time > start_time):
        print("\nPOLYGON VERIFIED: New equity data ingested.")
    else:
        print("\nPOLYGON STALE: No new equity data.")

if __name__ == '__main__':
    asyncio.run(verify_polygon())
