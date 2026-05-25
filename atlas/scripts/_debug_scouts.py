"""
Debug script: Check why scout_signals is empty.
Queries all scout-related tables to find where the chain breaks.
"""
import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas.config.settings import settings
import asyncpg


async def main():
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    conn = await asyncpg.connect(db_url)

    # 1. Check scout source tables
    tables = ['market_regime_memory', 'liquidity_intelligence', 'correlation_memory', 'execution_intelligence', 'external_scout_memory']
    print('=== SCOUT SOURCE TABLES ===')
    for t in tables:
        r = await conn.fetchrow(f'SELECT COUNT(*) FROM {t}')
        print(f'  {t}: {r[0]} rows')

    # 2. Check scout_signals
    r = await conn.fetchrow('SELECT COUNT(*) FROM scout_signals')
    print(f'\nscout_signals: {r[0]} rows')

    # 3. Check scout_mirror_debug_log
    r = await conn.fetchrow('SELECT COUNT(*) FROM scout_mirror_debug_log')
    print(f'scout_mirror_debug_log: {r[0]} rows')
    if r[0] > 0:
        rows = await conn.fetch('SELECT * FROM scout_mirror_debug_log ORDER BY created_at DESC LIMIT 10')
        for row in rows:
            print(f'  table={row["table_name"]} source={row["source"]} symbol={row["symbol"]} success={row["success"]} err={row["error_message"]}')

    # 4. Check failed_inserts
    r = await conn.fetchrow('SELECT COUNT(*) FROM failed_inserts')
    print(f'\nfailed_inserts: {r[0]} rows')
    if r[0] > 0:
        rows = await conn.fetch('SELECT table_name, reason, inserted_at FROM failed_inserts ORDER BY inserted_at DESC LIMIT 15')
        for row in rows:
            print(f'  table={row["table_name"]} reason={str(row["reason"])[:200]} inserted_at={row["inserted_at"]}')

    # 5. Sign of life from the last 2 hours
    r = await conn.fetchrow("SELECT COUNT(*) FROM scout_signals WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'\nscout_signals (last 2h): {r[0]} rows')

    # 6. Check market_data_l1 status
    r = await conn.fetchrow('SELECT COUNT(*) FROM market_data_l1')
    print(f'\nmarket_data_l1: {r[0]} rows')
    if r[0] > 0:
        r2 = await conn.fetchrow('SELECT COUNT(DISTINCT symbol) FROM market_data_l1')
        print(f'  distinct symbols: {r2[0]}')
        r3 = await conn.fetchrow('SELECT MIN(time), MAX(time) FROM market_data_l1')
        print(f'  time range: {r3[0]} to {r3[1]}')

    # 7. Sample scout table data
    for t in ['market_regime_memory', 'liquidity_intelligence', 'external_scout_memory']:
        r = await conn.fetchrow(f'SELECT COUNT(*) FROM {t}')
        if r[0] > 0:
            row = await conn.fetchrow(f'SELECT * FROM {t} ORDER BY timestamp DESC LIMIT 1')
            print(f'\nLatest {t} row:')
            for k, v in row.items():
                print(f'  {k}: {str(v)[:100]}')

    await conn.close()

asyncio.run(main())
