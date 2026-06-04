
import asyncio
from atlas.agents.l1_data.binance_rest_agent import BinanceWebSocketAgent
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
import redis.asyncio as redis
from sqlalchemy import text

async def run_ingestion_and_check():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    r_client = redis.from_url(settings.redis_url)
    
    agent = BinanceWebSocketAgent(r_client, settings.database_url)
    
    print("Starting Binance Ingestion Agent for 2 minutes...")
    # Start agent in a task
    # Note: Agent run() is usually an infinite loop. We'll stop it after some time.
    # We'll use a hacky way to stop it: set its status to STOPPED
    
    agent_task = asyncio.create_task(agent.run())
    
    # 1. Initial check
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'binance'"))
        start_time = r.scalar()
        print(f"Initial Last Tick: {start_time}")

    print("Waiting 130 seconds for 2 polling cycles...")
    await asyncio.sleep(130)
    
    # 2. Final check
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT MAX(time) FROM market_data_l1 WHERE source = 'binance'"))
        end_time = r.scalar()
        print(f"Final Last Tick:   {end_time}")
        
    await agent.stop()
    agent_task.cancel()
    
    if end_time and (start_time is None or end_time > start_time):
        print("\nLEVEL 3 VERIFIED: Data is flowing from Binance REST API.")
    else:
        print("\nLEVEL 3 FAILED: No new data ingested. Check API keys or network.")

if __name__ == '__main__':
    asyncio.run(run_ingestion_and_check())
