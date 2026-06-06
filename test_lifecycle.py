import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l5_execution.execution_gateway import ExecutionGateway
from atlas.agents.l5_execution.broker_adapter import SimulatorAdapter
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.core.event_lineage import EventLineageClient
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use a valid UUID for strategy_id
STRATEGY_ID = str(uuid.uuid4())

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect(run_migrations=False)
    redis = Redis()

    # Clean up any existing test data
    async with db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM positions WHERE symbol = 'AAPL'"))
        await conn.execute(text("DELETE FROM paper_trades WHERE symbol = 'AAPL'"))
        await conn.execute(text("DELETE FROM market_data_l1 WHERE symbol = 'AAPL'"))
        # Insert market data for AAPL: two timestamps with different prices
        now = datetime.utcnow()
        await conn.execute(text("""
            INSERT INTO market_data_l1 (symbol, time, open, high, low, close, volume)
            VALUES (:sym, :t1, 150, 151, 149, 150, 1000),
                   (:sym, :t2, 155, 156, 154, 155, 1000)
        """), {"sym": "AAPL", "t1": now - timedelta(minutes=5), "t2": now})

    broker = SimulatorAdapter(db_client=db, default_price=150.0)
    risk = RiskController(redis, db)
    lineage = EventLineageClient()
    gateway = ExecutionGateway(redis, db, broker, risk, lineage)

    # Start gateway background tasks (recovery, monitoring, etc.)
    # We'll just call execute directly for our test signals

    # Signal 1: BUY
    logger.info("=== SENDING BUY SIGNAL ===")
    await gateway.execute({
        "id": STRATEGY_ID,
        "symbol": "AAPL",
        "side": "buy",
        "qty": 10,
        "type": "validated"
    })

    await asyncio.sleep(0.5)

    # Check state after BUY
    async with db.engine.connect() as conn:
        pos = await conn.execute(text("SELECT * FROM positions WHERE symbol = 'AAPL'"))
        logger.info(f"Positions after BUY: {pos.fetchall()}")
        trades = await conn.execute(text("SELECT strategy_id, symbol, side, price, pnl FROM paper_trades WHERE symbol = 'AAPL'"))
        logger.info(f"Paper trades after BUY: {trades.fetchall()}")

    # Signal 2: SELL (close)
    logger.info("=== SENDING SELL SIGNAL ===")
    await gateway.execute({
        "id": STRATEGY_ID,
        "symbol": "AAPL",
        "side": "sell",
        "qty": 10,
        "type": "validated"
    })

    await asyncio.sleep(0.5)

    # Check state after SELL
    async with db.engine.connect() as conn:
        pos = await conn.execute(text("SELECT * FROM positions WHERE symbol = 'AAPL'"))
        logger.info(f"Positions after SELL: {pos.fetchall()}")
        trades = await conn.execute(text("SELECT strategy_id, symbol, side, price, pnl FROM paper_trades WHERE symbol = 'AAPL' ORDER BY time"))
        logger.info(f"Paper trades after SELL: {trades.fetchall()}")

    # Also check realized pnl calculation
    async with db.engine.connect() as conn:
        trades = await conn.execute(text("SELECT side, price, pnl FROM paper_trades WHERE symbol = 'AAPL' ORDER BY time"))
        for row in trades.fetchall():
            logger.info(f"Trade: side={row.side}, price={row.price}, pnl={row.pnl}")

    await db.close()
    await redis.close()

if __name__ == "__main__":
    asyncio.run(main())
