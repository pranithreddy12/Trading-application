import asyncio
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings

async def main(name: str):
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text('''
            SELECT bt.*, bt.results::text as results_text
            FROM backtest_results bt
            JOIN strategies s ON s.id = bt.strategy_id
            WHERE s.name = :name
            ORDER BY bt.created_at DESC
            LIMIT 5
        '''), {"name": name})
        rows = r.fetchall()
        for row in rows:
            print('---')
            print('mapping keys:', list(row._mapping.keys()))
            print('results:', row.results_text[:800])

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python scripts/tools/inspect_backtest_results.py <strategy_name>')
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
