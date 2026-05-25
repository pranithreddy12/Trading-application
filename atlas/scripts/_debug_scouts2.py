"""
Debug script: Check market data status for scout computations.
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

    # Check market_data_l1 details
    r = await conn.fetchrow('SELECT COUNT(*) FROM market_data_l1')
    print(f'market_data_l1 total rows: {r[0]}')
    
    if r[0] > 0:
        # What symbols are there?
        rows = await conn.fetch('SELECT symbol, COUNT(*) as cnt FROM market_data_l1 GROUP BY symbol ORDER BY cnt DESC LIMIT 15')
        for row in rows:
            print(f'  symbol={row["symbol"]}: {row["cnt"]} bars')
        
        # Time range
        r = await conn.fetchrow('SELECT MIN(time), MAX(time) FROM market_data_l1')
        print(f'  time range: {r["min"]} to {r["max"]}')
        
        # Do any symbols have enough bars for scouts (need 30-500)
        rows = await conn.fetch('SELECT symbol, COUNT(*) as cnt FROM market_data_l1 GROUP BY symbol HAVING COUNT(*) >= 30 ORDER BY cnt DESC')
        print(f'\nSymbols with >= 30 bars: {len(rows)}')
        for row in rows[:5]:
            print(f'  {row["symbol"]}: {row["cnt"]} bars')

        # Check for BTCUSDT specifically
        r = await conn.fetchrow("SELECT COUNT(*) FROM market_data_l1 WHERE symbol = 'BTCUSDT'")
        print(f'\nBTCUSDT bars: {r[0]}')
        
        # Check if the data is recent enough
        r = await conn.fetchrow("SELECT MAX(time) FROM market_data_l1 WHERE symbol = 'BTCUSDT'")
        if r[0]:
            print(f'  Latest BTCUSDT time: {r[0]}')
    
    # Check what other data sources might exist
    tables = ['features', 'market_data_l2', 'order_flow']
    for t in tables:
        try:
            r = await conn.fetchrow(f'SELECT COUNT(*) FROM {t}')
            print(f'\n{t}: {r[0]} rows')
            if r[0] > 0:
                r2 = await conn.fetchrow(f'SELECT MIN(time), MAX(time) FROM {t}')
                print(f'  time range: {r2[0]} to {r2[1]}')
        except Exception as e:
            print(f'\n{t}: ERROR - {e}')

    await conn.close()

asyncio.run(main())
