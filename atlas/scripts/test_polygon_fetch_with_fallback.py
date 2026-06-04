#!/usr/bin/env python
import asyncio
from datetime import datetime, timezone

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient, BarData
from atlas.data.ingestion.polygon_rest_client import PolygonRestClient

try:
    from atlas.data.ingestion.yfinance_client import fetch_1m_bars
except Exception as exc:
    fetch_1m_bars = None
    print("yfinance fallback not available:", exc)


async def main():
    settings = get_settings()
    ts = TimescaleClient(settings.database_url)
    await ts.connect()

    async def bar_handler(data, symbol):
        bar = BarData(
            time=datetime.fromtimestamp(data["time"] / 1000, tz=timezone.utc),
            symbol=symbol,
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=float(data.get("volume", 0)),
            source="polygon",
            interval="1m",
            asset_class="equity",
        )
        try:
            await ts.write_bars(symbol, bar)
            print("WROTE_BAR", symbol, data["time"])
        except Exception as e:
            print("WRITE_ERROR", e)
            raise

    client = PolygonRestClient(
        api_key=settings.polygon_api_key,
        symbols=["AAPL"],
        bar_handler=bar_handler,
        poll_bars=5.0,
        calls_per_minute=60,
        fallback_fetch=fetch_1m_bars,
    )

    await client.start()
    # allow one poll cycle
    await asyncio.sleep(12)
    await client.stop()

    max_time = await ts.fetchval(
        "SELECT MAX(time) FROM market_data_l1 WHERE symbol = :s AND source = 'polygon'",
        {"s": "AAPL"},
    )
    recent_count = await ts.fetchval(
        "SELECT COUNT(*) FROM market_data_l1 WHERE symbol = :s AND source = 'polygon' AND time > now() - interval '15 minutes'",
        {"s": "AAPL"},
    )
    print("DB_MAX_TIME", max_time, "RECENT_COUNT", recent_count)

    await ts.close()


if __name__ == "__main__":
    asyncio.run(main())
