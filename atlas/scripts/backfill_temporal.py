import asyncio
import json
from loguru import logger
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.short_window_evaluator import score_temporal_consistency

async def backfill():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT b.strategy_id, b.results 
                FROM backtest_results b
                JOIN strategies s ON s.id = b.strategy_id
                WHERE s.status IN ('validated', 'research_candidate')
            """)
        )
        rows = result.fetchall()
        
    updated = 0
    for row in rows:
        sid = row[0]
        res = row[1]
        
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except:
                continue
        
        # If there's holdout, test, train sharpe, we can use those as "windows"
        windows = []
        if 'train_sharpe' in res: windows.append(res['train_sharpe'])
        if 'test_sharpe' in res: windows.append(res['test_sharpe'])
        if 'holdout_sharpe' in res: windows.append(res['holdout_sharpe'])
        
        if len(windows) >= 2:
            tc = score_temporal_consistency(windows)
            res['temporal_consistency'] = tc
            
            # Update backtest_results
            async with db.engine.begin() as conn:
                await conn.execute(
                    text("UPDATE backtest_results SET results = :res WHERE strategy_id = :sid"),
                    {"res": json.dumps(res), "sid": sid}
                )
            updated += 1

    print(f"Backfilled temporal consistency for {updated} strategies.")

if __name__ == "__main__":
    asyncio.run(backfill())
