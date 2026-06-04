import asyncio
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy import text

async def main():
    db = TimescaleClient(get_settings().database_url)
    await db.connect(run_migrations=False)
    async with db.engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT leader_order_id, symbol, side, leader_qty, follower_qty, latency_ms, status, created_at
            FROM copy_execution_log
            ORDER BY created_at DESC
            LIMIT 10
        """))
        print("\n--- Recent Copy Trading Executions ---")
        rows = res.fetchall()
        if not rows:
            print("No copy executions found.")
            return
        print(f"{'Leader Order ID':<38} {'Symbol':<8} {'Side':<5} {'L_Qty':<8} {'F_Qty':<8} {'Latency':<8} {'Status':<10}")
        print("-" * 90)
        for r in rows:
            leader_order_id = str(r[0])
            symbol = r[1]
            side = r[2]
            l_qty = float(r[3])
            f_qty = float(r[4])
            latency = f"{r[5]}ms" if r[5] is not None else "N/A"
            status = r[6]
            print(f"{leader_order_id:<38} {symbol:<8} {side:<5} {l_qty:<8.2f} {f_qty:<8.2f} {latency:<8} {status:<10}")
    await db.close()

if __name__ == '__main__':
    asyncio.run(main())
