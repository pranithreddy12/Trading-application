
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text
import time

async def watch_trades():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
        initial_count = r.scalar()
        print(f"Initial paper_trades count: {initial_count}")
        print("Waiting for full_autonomous_cycle to promote a strategy and place a trade...")

        start_time = time.time()
        while time.time() - start_time < 300: # Wait up to 5 minutes
            r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
            current_count = r.scalar()
            
            if current_count > initial_count:
                print(f"\nSUCCESS! New trades detected! Count went from {initial_count} -> {current_count}")
                
                # Fetch the newest trades
                limit = current_count - initial_count
                r2 = await conn.execute(text(f"""
                    SELECT p.symbol, p.side, p.quantity, p.price, p.pnl, s.name, p.time
                    FROM paper_trades p
                    LEFT JOIN strategies s ON p.strategy_id::text = s.id::text
                    ORDER BY p.time DESC
                    LIMIT {limit}
                """))
                new_trades = r2.fetchall()
                print("\n--- NEW LIVE TRADES FROM AUTONOMOUS CYCLE ---")
                for t in new_trades:
                    print(f"[{t[6]}] {t[5]}")
                    print(f"  Action: {t[1].upper()} {t[2]} {t[0]} @ ${t[3]}")
                    print(f"  PnL: ${t[4]}")
                    print("-" * 50)
                
                return
                
            await asyncio.sleep(5)
            
        print("Timeout waiting for new trades. The cycle might take longer.")

if __name__ == '__main__':
    asyncio.run(watch_trades())
