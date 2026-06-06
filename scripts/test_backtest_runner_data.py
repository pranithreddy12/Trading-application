
import asyncio
import pandas as pd
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def test_backtest_data():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    
    async with db.engine.connect() as conn:
        print("1. Looking for recent backtests...")
        r = await conn.execute(text("""
            SELECT s.name, br.bars_processed, br.start_date, br.end_date, br.composite_fitness_score
            FROM backtest_results br
            JOIN strategies s ON s.id = br.strategy_id
            ORDER BY br.created_at DESC
            LIMIT 5
        """))
        results = r.fetchall()
        
        if not results:
            print("No backtest results found yet.")
        else:
            print(f"\n{'STRATEGY':<35} | {'BARS':<6} | {'START DATE':<20} | {'END DATE':<20} | {'SCORE'}")
            print("-" * 110)
            for row in results:
                print(f"{str(row[0])[:35]:<35} | {row[1]:<6} | {str(row[2])[:19]:<20} | {str(row[3])[:19]:<20} | {row[4]}")

        # Check if we have strategies stuck in coded
        r2 = await conn.execute(text("SELECT COUNT(*) FROM strategies WHERE status = 'coded'"))
        print(f"\nStrategies waiting to be backtested: {r2.scalar()}")
        
        # We can forcibly set a strategy to 'coded' to let BacktestRunner process it
        print("Pushing 1 strategy to 'coded' to force a fresh backtest...")
        await conn.execute(text("""
            UPDATE strategies 
            SET status = 'coded' 
            WHERE id IN (
                SELECT id FROM strategies WHERE status IN ('validated', 'backtest_failed') LIMIT 1
            )
        """))
        conn.commit()

if __name__ == '__main__':
    asyncio.run(test_backtest_data())
