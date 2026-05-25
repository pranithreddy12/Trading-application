"""
diagnostic: simulate what the scouts do — call fetch_recent_bars and check data.
"""
import asyncio
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

    print("=== Simulating scout fetch_recent_bars ===")
    for sym in symbols:
        df = await db.fetch_recent_bars(sym, limit=500)
        if df is None or len(df) == 0:
            print(f"  {sym}: EMPTY (no bars)")
        else:
            bar_count = len(df)
            times = df["time"]
            print(f"  {sym}: {bar_count} bars, {times.min()} to {times.max()}, latest={times.max()}")

    # Also check which tables exist
    print()
    print("=== Checking key tables ===")
    async with db.engine.connect() as conn:
        from sqlalchemy.sql import text
        for tbl in ["paper_trades", "execution_log", "market_data_l2"]:
            try:
                r = (await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))).scalar()
                print(f"  {tbl}: {r} rows")
            except Exception as e:
                print(f"  {tbl}: ERROR - {e}")

    await db.close()


asyncio.run(main())
