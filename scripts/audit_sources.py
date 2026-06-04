
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def audit_sources():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        print("--- Market Data Source Audit ---")
        r = await conn.execute(text("SELECT source, COUNT(*), MAX(time) FROM market_data_l1 GROUP BY source"))
        for row in r.fetchall():
            print(f"Source: {row[0]:<12} | Count: {row[1]:<8} | Latest: {row[2]}")

if __name__ == '__main__':
    asyncio.run(audit_sources())
