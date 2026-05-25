"""
Check current database state before running Phase 26H soak.
"""
import asyncio
import re
from atlas.config.settings import settings
import asyncpg


async def check():
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    conn = await asyncpg.connect(db_url)

    # Market data freshness
    r = await conn.fetchrow('SELECT COUNT(*), MIN(time), MAX(time) FROM market_data_l1')
    print(f'market_data_l1: {r[0]} rows, {r[1]} to {r[2]}')

    # Scout source tables
    for tbl in ['market_regime_memory', 'liquidity_intelligence', 'correlation_memory', 'execution_intelligence']:
        try:
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = $1 ORDER BY column_name",
                tbl
            )
            col_names = [c[0] for c in cols]
            ts_col = next((c for c in ['created_at', 'timestamp', 'time'] if c in col_names), None)
            if ts_col:
                r = await conn.fetchrow(f'SELECT COUNT(*), MAX({ts_col}) FROM {tbl}')
                print(f'  {tbl}: {r[0]} rows, latest_{ts_col}={r[1]}')
            else:
                r = await conn.fetchrow(f'SELECT COUNT(*) FROM {tbl}')
                print(f'  {tbl}: {r[0]} rows (no timestamp col found)')
        except Exception as e:
            print(f'  {tbl}: ERROR - {e}')

    # Scout signals
    try:
        r = await conn.fetchrow('SELECT COUNT(*), MAX(created_at) FROM scout_signals')
        print(f'scout_signals: {r[0]} rows, latest={r[1]}')
    except Exception as e:
        print(f'scout_signals: ERROR - {e}')

    # Strategies
    r = await conn.fetchrow('SELECT COUNT(*) FROM strategies')
    print(f'strategies: {r[0]}')
    if r[0] > 0:
        r2 = await conn.fetchrow('SELECT MAX(created_at) FROM strategies')
        print(f'  latest: {r2[0]}')

    # Scout influence log / attribution
    for tbl in ['scout_influence_log', 'scout_economic_attribution']:
        try:
            r = await conn.fetchrow(f'SELECT COUNT(*), MAX(created_at) FROM {tbl}')
            print(f'{tbl}: {r[0]} rows, latest={r[1]}')
        except Exception as e:
            print(f'{tbl}: ERROR - {e}')

    # Source performance log
    try:
        r = await conn.fetchrow('SELECT COUNT(*), MAX(updated_at) FROM source_performance_log')
        print(f'source_performance_log: {r[0]} rows, latest={r[1]}')
    except Exception as e:
        print(f'source_performance_log: ERROR - {e}')

    # Paper trades
    try:
        r = await conn.fetchrow('SELECT COUNT(*), MAX(created_at) FROM paper_trades')
        print(f'paper_trades: {r[0]} rows, latest={r[1]}')
    except Exception as e:
        print(f'paper_trades: ERROR - {e}')

    await conn.close()


asyncio.run(check())
