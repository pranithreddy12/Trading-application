
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text
import pandas as pd

async def check():
    c = TimescaleClient(db_url=settings.database_url)
    await c.connect()
    try:
        async with c.engine.connect() as conn:
            # Get all paper trades
            r = await conn.execute(text('SELECT strategy_id, symbol, side, quantity, price, time FROM paper_trades ORDER BY time ASC'))
            trades = r.fetchall()
            df = pd.DataFrame(trades, columns=["strategy_id", "symbol", "side", "quantity", "price", "time"])
            
            print(f"Total trades: {len(df)}")
            
            # Check for round trips
            # Group by strategy and symbol
            groups = df.groupby(["strategy_id", "symbol"])
            for (sid, sym), group in groups:
                if len(group) > 1:
                    # print(f"\nStrategy {sid} on {sym} has {len(group)} trades:")
                    
                    # Try to calculate what PnL should have been
                    pos = 0
                    avg_price = 0
                    total_pnl = 0
                    for _, row in group.iterrows():
                        side = row["side"].lower()
                        qty = float(row["quantity"])
                        price = float(row["price"])
                        
                        if pos == 0:
                            pos = qty if side == "buy" else -qty
                            avg_price = price
                        else:
                            # Check if closing/reducing
                            if (pos > 0 and side == "sell") or (pos < 0 and side == "buy"):
                                # Realized PnL
                                realized_qty = min(abs(pos), qty)
                                if pos > 0:
                                    pnl = realized_qty * (price - avg_price)
                                else:
                                    pnl = realized_qty * (avg_price - price)
                                total_pnl += pnl
                                
                                # Update pos
                                if pos > 0: pos -= qty
                                else: pos += qty
                            else:
                                # Increasing
                                new_pos = pos + (qty if side == "buy" else -qty)
                                if new_pos != 0:
                                    avg_price = (avg_price * abs(pos) + price * qty) / abs(new_pos)
                                else:
                                    avg_price = 0
                                pos = new_pos
                    
                    if abs(total_pnl) > 0.001:
                        print(f"Strategy {sid} on {sym} SHOULD HAVE PnL: {total_pnl}")

    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(check())
