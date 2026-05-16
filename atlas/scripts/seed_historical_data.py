import asyncio
import aiohttp
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient, _r4, _r6
from atlas.config.settings import settings

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
INTERVAL = "1m"
LIMIT = 500  # max per request, gives ~8 hours of 1m bars


async def fetch_binance_klines(
    session: aiohttp.ClientSession, symbol: str, interval: str = "1m", limit: int = 500
) -> list:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with session.get(url, params=params) as resp:
        if resp.status == 200:
            return await resp.json()
        else:
            text_body = await resp.text()
            logger.error(f"Binance klines failed {resp.status}: {text_body}")
            return []


async def insert_bars(db: TimescaleClient, symbol: str, klines: list):
    """Insert klines into market_data_l1"""
    if not klines:
        return 0

    rows = []
    for k in klines:
        rows.append(
            {
                "time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                "symbol": symbol,
                "open": _r4(k[1]),
                "high": _r4(k[2]),
                "low": _r4(k[3]),
                "close": _r4(k[4]),
                "volume": _r6(k[5]),
                "source": "binance",
                "interval": "1m",
            }
        )

    async with db.engine.begin() as conn:
        # Use ON CONFLICT to avoid duplicate inserts
        await conn.execute(
            text("""
                INSERT INTO market_data_l1
                    (time, symbol, open, high, low, close, volume, source, interval)
                SELECT
                    d.time, d.symbol, d.open, d.high, d.low,
                    d.close, d.volume, d.source, d.interval
                FROM jsonb_to_recordset(cast(:rows_json as jsonb)) AS d(
                    time timestamptz, symbol text,
                    open float8, high float8, low float8,
                    close float8, volume float8,
                    source text, interval text
                )
                ON CONFLICT (time, symbol) DO NOTHING
            """),
            {
                "rows_json": __import__("json").dumps(
                    [{**r, "time": r["time"].isoformat()} for r in rows]
                )
            },
        )
    return len(rows)


async def main():
    db = TimescaleClient("postgresql+asyncpg://postgres:password@localhost:5433/atlas")
    await db.connect()

    # Check existing data first
    async with db.engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM market_data_l1"))
        existing = result.scalar()
    logger.info(f"Existing rows in market_data_l1: {existing}")

    resolver = aiohttp.AsyncResolver(nameservers=["8.8.8.8", "1.1.1.1", "8.8.4.4"])
    connector = aiohttp.TCPConnector(resolver=resolver)

    async with aiohttp.ClientSession(connector=connector) as session:
        for symbol in SYMBOLS:
            logger.info(f"Fetching {LIMIT} bars for {symbol}...")
            klines = await fetch_binance_klines(session, symbol, INTERVAL, LIMIT)

            if klines:
                inserted = await insert_bars(db, symbol, klines)
                logger.info(f"  {symbol}: inserted {inserted} bars")
            else:
                logger.warning(f"  {symbol}: no data returned")

            await asyncio.sleep(0.5)  # rate limit respect

    # Verify
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT symbol, COUNT(*) as bars,
                       MIN(time) as oldest,
                       MAX(time) as newest
                FROM market_data_l1
                GROUP BY symbol
                ORDER BY symbol
            """)
        )
        rows = result.fetchall()

    logger.info("=" * 60)
    logger.info("SEED COMPLETE — market_data_l1 contents:")
    for r in rows:
        logger.info(
            f"  {r.symbol}: {r.bars} bars | "
            f"{r.oldest.strftime('%H:%M')} → {r.newest.strftime('%H:%M')}"
        )
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
