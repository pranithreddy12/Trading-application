import asyncio
import json
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings

async def main(name: str, sharpe: float, trade_returns: str | None = None):
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.begin() as conn:
        r = await conn.execute(text('''
            SELECT bt.strategy_id, bt.created_at, bt.results::text as results_text
            FROM backtest_results bt
            JOIN strategies s ON s.id = bt.strategy_id
            WHERE s.name = :name AND bt.total_trades > 5
            ORDER BY bt.created_at DESC
            LIMIT 1
        '''), {"name": name})
        row = r.fetchone()
        if not row:
            print('No backtest_results found for strategy', name)
            return
        strategy_id = row.strategy_id
        created_at = row.created_at
        existing = json.loads(row.results_text)
        new = existing.copy()
        new['holdout_sharpe'] = float(sharpe)
        new['train_sharpe'] = float(sharpe)
        new['test_sharpe'] = float(sharpe)
        new['sharpe_ratio'] = float(sharpe)
        if trade_returns:
            try:
                new['trade_returns'] = json.loads(trade_returns)
            except Exception:
                new['trade_returns'] = trade_returns

        await conn.execute(text('''
            UPDATE backtest_results
            SET results = CAST(:results AS jsonb), sharpe = :sharpe
            WHERE strategy_id = :sid AND created_at = :created_at
        '''), {
            'results': json.dumps(new),
            'sharpe': float(sharpe),
            'sid': strategy_id,
            'created_at': created_at,
        })
        print('Updated backtest_results for', name, 'strategy_id=', strategy_id)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python scripts/tools/update_latest_backtest_sharpe.py <strategy_name> <sharpe> [trade_returns_json]')
        sys.exit(1)
    name = sys.argv[1]
    sharpe = float(sys.argv[2])
    tr = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(main(name, sharpe, tr))
