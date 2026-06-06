
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text
import pandas as pd

async def audit():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            # 1. Transitions: OPEN -> CLOSED
            # In the current schema, 'closed' positions are DELETED from the positions table.
            # We look for 'filled' paper_trades that reduced or closed a position.
            r = await conn.execute(text("SELECT status, COUNT(*) FROM positions GROUP BY status"))
            print("Current Position Statuses:")
            for row in r.fetchall():
                print(row)
            
            # 2. Check for duplicate positions (strategy_id + symbol)
            r = await conn.execute(text("SELECT strategy_id, symbol, COUNT(*) FROM positions GROUP BY strategy_id, symbol HAVING COUNT(*) > 1"))
            dupes = r.fetchall()
            print(f"\nDuplicate positions (sid + sym): {len(dupes)}")
            for d in dupes[:5]:
                print(d)

            # 3. Check paper_trades for round trips (approximate closure count)
            # A closure is usually a trade that has a non-zero pnl now (after fix) or 
            # where the running quantity for a (sid, sym) hits 0.
            r = await conn.execute(text("SELECT strategy_id, symbol, side, quantity, price, pnl FROM paper_trades ORDER BY time ASC"))
            trades = r.fetchall()
            df = pd.DataFrame(trades, columns=["sid", "sym", "side", "qty", "price", "pnl"])
            
            closed_count = 0
            open_permanently = 0
            
            groups = df.groupby(["sid", "sym"])
            for (sid, sym), group in groups:
                pos = 0
                for _, row in group.iterrows():
                    q = float(row["qty"])
                    if row["side"].lower() == "buy":
                        pos += q
                    else:
                        pos -= q
                
                if abs(pos) < 0.001:
                    closed_count += 1
                else:
                    open_permanently += 1
            
            print(f"\nLifecycle Stats (from paper_trades history):")
            print(f"Total Unique (Strategy, Symbol) Pairs: {len(groups)}")
            print(f"Fully Closed Pairs: {closed_count}")
            print(f"Currently Open Pairs: {open_permanently}")

            # 4. Check positions table for PnL persistence
            r = await conn.execute(text("SELECT SUM(realized_pnl) FROM positions"))
            print(f"\nSum of realized_pnl in positions table: {r.scalar()}")

    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(audit())
