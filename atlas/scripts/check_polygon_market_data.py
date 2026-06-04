import asyncio
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy.sql import text


async def main():
    db_url = settings.database_url
    client = TimescaleClient(db_url)
    try:
        await client.connect()
        async with client.engine.connect() as conn:
            # symbols from watchlist
            watchlist = []
            if settings.watchlist:
                watchlist = [s.strip() for s in settings.watchlist.split(',') if s.strip()]
            if not watchlist:
                watchlist = ['AAPL', 'SPY', 'QQQ']

            for sym in watchlist:
                q_max = text("SELECT MAX(time) FROM market_data_l1 WHERE source='polygon' AND symbol = :s")
                res = await conn.execute(q_max, {"s": sym})
                row = res.fetchone()
                max_time = row[0] if row is not None else None

                q_count = text("SELECT COUNT(*) FROM market_data_l1 WHERE source='polygon' AND symbol = :s AND time >= NOW() - INTERVAL '15 minutes'")
                cres = await conn.execute(q_count, {"s": sym})
                crow = cres.fetchone()
                recent_count = int(crow[0]) if crow is not None and crow[0] is not None else 0

                print(f"{sym}: polygon_max_time={max_time} recent_15m_count={recent_count}")

    finally:
        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
