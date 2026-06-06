
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text

async def check_historic_data():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    async with db.engine.connect() as conn:
        tables = [
            'market_data_l1', 
            'market_data_l2', 
            'features', 
            'features_wide',
            'strategies', 
            'backtest_results', 
            'mutation_memory',
            'positions',
            'paper_trades'
        ]
        print("--- Table Row Counts ---")
        for t in tables:
            try:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                print(f"{t}: {r.scalar()} rows")
            except Exception as e:
                print(f"{t}: Error - {e}")

if __name__ == '__main__':
    asyncio.run(check_historic_data())
