
import asyncio
import json
import uuid
import random
from sqlalchemy import text
from redis.asyncio import Redis

from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from atlas.agents.l5_execution.execution_gateway import ExecutionGateway
from atlas.agents.l5_execution.broker_adapter import SimulatorAdapter
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.core.event_lineage import EventLineageClient
from atlas.agents.l7_meta.deployment_governor import DeploymentGovernor

async def test_enhanced_gateway():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    redis = Redis.from_url(settings.redis_url)
    
    # 1. Setup ExecutionGateway dependencies
    broker = SimulatorAdapter(default_price=150.0, fill_latency_ms=10)
    risk = RiskController(redis, db)
    lineage = EventLineageClient(db)
    
    gateway = ExecutionGateway(redis, db, broker, risk, lineage)
    await gateway.start()
    
    # Wait for ready
    for _ in range(10):
        if gateway._recovery_complete:
            break
        await asyncio.sleep(1)

    print("Testing 3 unique strategy activations...")
    
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT id, name FROM strategies WHERE status = 'validated' ORDER BY RANDOM() LIMIT 3"))
        strategies = r.fetchall()

    gov = DeploymentGovernor(redis, db)
    
    for i, strat in enumerate(strategies):
        strat_id = str(strat[0])
        dep_id = f"enhanced-test-{uuid.uuid4().hex[:8]}"
        
        async with db.engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO deployment_governance (id, strategy_id, mode, status, proposed_by, proposed_at)
                VALUES (:id, :sid, 'paper', 'approved', 'enhanced-test', NOW())
            """), {"id": dep_id, "sid": strat_id})

        print(f"Triggering activation for: {strat[1]}...")
        await gov.execute_deployment(dep_id)
        await asyncio.sleep(3) # Wait for processing

    # Final Verification
    print("\n--- NEW PAPER TRADES (LAST 3) ---")
    async with db.engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT symbol, side, price, pnl, time 
            FROM paper_trades 
            ORDER BY time DESC 
            LIMIT 3
        """))
        for row in r.fetchall():
            print(f"Symbol: {row[0]:<8} | {row[1]:<4} | Price: ${row[2]:<8.2f} | PnL: ${row[3]:>8.2f} | Time: {row[4]}")

    await gateway.stop()
    await redis.aclose()

if __name__ == '__main__':
    asyncio.run(test_enhanced_gateway())
