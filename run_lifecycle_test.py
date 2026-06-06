import asyncio, logging, uuid
from datetime import datetime, timedelta
from sqlalchemy import text

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l5_execution.execution_gateway import ExecutionGateway
from atlas.agents.l5_execution.broker_adapter import SimulatorAdapter
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.core.event_lineage import EventLineageClient
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRATEGY_ID = str(uuid.uuid4())

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect(run_migrations=False)
    redis = Redis()

    # Clean up test data and insert market data with different prices
    async with db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM positions WHERE symbol = 'AAPL'"))
        await conn.execute(text("DELETE FROM paper_trades WHERE symbol = 'AAPL'"))
        await conn.execute(text("DELETE FROM market_data_l1 WHERE symbol = 'AAPL'"))
        now = datetime.utcnow()
        await conn.execute(text("""
            INSERT INTO market_data_l1 (symbol, time, open, high, low, close, volume, source)
            VALUES ('AAPL', :t1, 150, 151, 149, 150, 1000, 'test'),
                   ('AAPL', :t2, 155, 156, 154, 155, 1000, 'test')
        """), {"t1": now - timedelta(minutes=10), "t2": now - timedelta(minutes=5)})

    broker = SimulatorAdapter(db_client=db)
    risk = RiskController(redis, db)
    lineage = EventLineageClient(db)
    gateway = ExecutionGateway(redis, db, broker, risk, lineage)

    # BUY signal
    logger.info("=== BUY SIGNAL ===")
    await gateway.execute({"id": STRATEGY_ID, "symbol": "AAPL", "side": "buy", "qty": 10, "type": "validated"})
    await asyncio.sleep(0.5)

    async with db.engine.connect() as conn:
        pos = await conn.execute(text("SELECT symbol, side, qty, avg_price FROM positions WHERE symbol = 'AAPL'"))
        rows = pos.fetchall()
        logger.info(f"Positions after BUY: {rows}")

    # SELL signal (close)
    logger.info("=== SELL SIGNAL ===")
    await gateway.execute({"id": STRATEGY_ID, "symbol": "AAPL", "side": "sell", "qty": 10, "type": "validated"})
    await asyncio.sleep(0.5)

    async with db.engine.connect() as conn:
        pos = await conn.execute(text("SELECT symbol, side, qty, avg_price FROM positions WHERE symbol = 'AAPL'"))
        rows = pos.fetchall()
        logger.info(f"Positions after SELL: {rows}")

    async with db.engine.connect() as conn:
        trades = await conn.execute(text("SELECT symbol, side, price, pnl FROM paper_trades WHERE symbol = 'AAPL' ORDER BY time"))
        for r in trades.fetchall():
            logger.info(f"Trade: symbol={r[0]}, side={r[1]}, price={r[2]}, pnl={r[3]}")

    await db.close()
    await redis.close()

if __name__ == "__main__":
    asyncio.run(main())