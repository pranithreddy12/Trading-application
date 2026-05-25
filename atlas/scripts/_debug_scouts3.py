"""
Debug script: Check timing of scout data vs scout_signals.
Find out when the last scout_signals entry was created.
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

    # 1. When was the LAST scout_signals entry created?
    r = await conn.fetchrow('SELECT MAX(created_at) FROM scout_signals')
    print(f'Latest scout_signals: {r[0]}')
    
    # 2. How many scout_signals per day?
    r = await conn.fetch('SELECT DATE(created_at) as d, COUNT(*) as cnt FROM scout_signals GROUP BY d ORDER BY d DESC')
    print(f'\nscout_signals by date:')
    for row in r:
        print(f'  {row["d"]}: {row["cnt"]}')
    
    # 3. When was the LAST market_regime_memory entry created?
    r = await conn.fetchrow('SELECT MAX(timestamp) FROM market_regime_memory')
    print(f'\nLatest market_regime_memory: {r[0]}')
    
    # 4. Check if there are data from today
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    print(f'\nCurrent time (UTC): {now}')
    
    r = await conn.fetchrow("SELECT COUNT(*) FROM market_regime_memory WHERE timestamp > NOW() - INTERVAL '24 hours'")
    print(f'market_regime_memory (last 24h): {r[0]} rows')
    
    r = await conn.fetchrow("SELECT MAX(timestamp) FROM market_regime_memory WHERE timestamp > NOW() - INTERVAL '24 hours'")
    print(f'market_regime_memory latest in 24h: {r[0]}')
    
    # 5. Check the scout_mirror_debug_log timing
    r = await conn.fetchrow('SELECT MAX(created_at) FROM scout_mirror_debug_log')
    print(f'\nLatest scout_mirror_debug_log: {r[0]}')
    
    r = await conn.fetchrow("SELECT COUNT(*) FROM scout_mirror_debug_log WHERE created_at > NOW() - INTERVAL '24 hours'")
    print(f'scout_mirror_debug_log (last 24h): {r[0]} rows')
    
    # 6. Check complete scout data freshness
    print(f'\n=== DATA FRESHNESS SUMMARY ===')
    for t in ['market_regime_memory', 'liquidity_intelligence', 'correlation_memory', 'execution_intelligence']:
        r = await conn.fetchrow(f'SELECT MAX(timestamp) FROM {t}')
        print(f'{t}: latest = {r[0]}')
    
    # 7. What about the sources in scout_signals?
    r = await conn.fetch('SELECT source, COUNT(*) as cnt, MAX(created_at) as last FROM scout_signals GROUP BY source ORDER BY last DESC')
    print(f'\nscout_signals sources with latest:')
    for row in r:
        print(f'  {row["source"]}: {row["cnt"]} rows, last={row["last"]}')

    await conn.close()

asyncio.run(main())
