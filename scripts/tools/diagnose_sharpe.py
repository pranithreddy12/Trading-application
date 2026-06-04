import asyncio
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings

async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        r = await conn.execute(text('''
            SELECT 
                bt.strategy_id,
                s.name,
                bt.total_trades,
                bt.win_rate,
                bt.max_drawdown,
                bt.results->>'holdout_sharpe' as sharpe,
                bt.results::text as results_text
            FROM backtest_results bt
            JOIN strategies s ON s.id = bt.strategy_id
            WHERE bt.total_trades > 5
            ORDER BY bt.win_rate DESC
            LIMIT 5
        '''))
        rows = r.fetchall()
        for row in rows:
            print(f'{row.name}: trades={row.total_trades} wr={row.win_rate:.2f} sharpe={row.sharpe}')
            print(f'  results: {row.results_text[:800]}')

if __name__ == '__main__':
    asyncio.run(main())
