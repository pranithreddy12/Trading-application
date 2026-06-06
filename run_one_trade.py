import asyncio, logging
from atlas.agents.l5_execution.execution_gateway import ExecutionGateway
from atlas.agents.l5_execution.broker_adapter import SimulatorAdapter
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.core.event_lineage import EventLineageClient
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect(run_migrations=False)
    redis = Redis()
    broker = SimulatorAdapter(db_client=db)
    risk = RiskController()
    lineage = EventLineageClient()
    gateway = ExecutionGateway(redis, db, broker, risk, lineage)
    # Start gateway background tasks
    asyncio.create_task(gateway.run())
    # Wait a moment
    await asyncio.sleep(1)
    # Send BUY signal
    await gateway._track_background_task(asyncio.create_task(gateway.execute({"id":"s1","symbol":"AAPL","side":"buy","qty":10,"type":"validated"})))
    await asyncio.sleep(1)
    # Send SELL signal to close
    await gateway._track_background_task(asyncio.create_task(gateway.execute({"id":"s1","symbol":"AAPL","side":"sell","qty":10,"type":"validated"})))
    await asyncio.sleep(2)
    # Dump DB state
    async with db.engine.connect() as conn:
        positions = await conn.execute("SELECT * FROM positions WHERE strategy_id='s1'")
        print('POSITIONS:', positions.fetchall())
        trades = await conn.execute("SELECT strategy_id,symbol,side,price,pnl FROM paper_trades WHERE strategy_id='s1' ORDER BY time DESC")
        print('TRADES:', trades.fetchall())
    await db.close()
    await redis.close()

asyncio.run(main())
