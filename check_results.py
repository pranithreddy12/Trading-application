import asyncio
from sqlalchemy import text
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect(run_migrations=False)

    async with db.engine.connect() as conn:
        # Positions
        pos = await conn.execute(text("SELECT symbol, side, qty, avg_price FROM positions"))
        print("=== POSITIONS ===")
        for r in pos.fetchall():
            print(f"  {r}")

        # Paper trades
        trades = await conn.execute(text("""
            SELECT time, strategy_id, symbol, side, quantity, price, pnl
            FROM paper_trades
            ORDER BY time DESC
            LIMIT 10
        """))
        print("\n=== PAPER TRADES ===")
        for r in trades.fetchall():
            print(f"  {r}")

        # Summary
        summary = await conn.execute(text("""
            SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE pnl <> 0) as non_zero_pnl, SUM(pnl) as total_pnl
            FROM paper_trades
        """))
        row = summary.fetchone()
        print(f"\n=== SUMMARY ===")
        print(f"  Total trades: {row[0]}")
        print(f"  Non-zero PnL rows: {row[1]}")
        print(f"  Total PnL: {row[2]}")

    await db.close()

asyncio.run(main())