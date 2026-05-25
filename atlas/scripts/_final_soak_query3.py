"""Phase 26H — Final Soak Results Query (v4 - ASCII safe)."""
import asyncio, re
from atlas.config.settings import settings
import asyncpg

async def check():
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    conn = await asyncpg.connect(db_url)

    print('=== FINAL PHASE 26H SOAK RESULTS ===')
    print(f'Report time: {await conn.fetchval("SELECT NOW()")}\n')

    # S1: Scout Signals
    r2 = await conn.fetchrow("SELECT COUNT(*), MAX(created_at) FROM scout_signals")
    r3 = await conn.fetchrow("SELECT COUNT(*) FROM scout_signals WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'S1 scout_signals total={r2[0]}, this_run={r3[0]}, latest={r2[1]}')

    rows = await conn.fetch("SELECT source, COUNT(*) as cnt FROM scout_signals WHERE created_at > NOW() - INTERVAL '2 hours' GROUP BY source ORDER BY cnt DESC")
    print(f'  sources this_run ({len(rows)}):')
    for r in rows: print(f'    {r[0]}: {r[1]}')

    # S2: Strategies
    r = await conn.fetchrow("SELECT COUNT(*), MAX(created_at) FROM strategies")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM strategies WHERE created_at > NOW() - INTERVAL '2 hours'")
    r3 = await conn.fetchrow("SELECT COUNT(*) FROM backtest_results WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'\nS2 strategies total={r[0]}, this_run={r2[0]}, latest={r[1]}')
    print(f'  backtest_results this_run={r3[0]}')

    # S3: Scout Influence
    r = await conn.fetchrow("SELECT COUNT(*) FROM scout_influence_log WHERE created_at > NOW() - INTERVAL '2 hours'")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution")
    print(f'\nS3 scout_influence_log_this_run={r[0]}')
    print(f'  scout_economic_attribution_total={r2[0]}')

    # S4: Trust Evolution
    r = await conn.fetchrow("SELECT COUNT(*) FROM source_performance_log WHERE updated_at > NOW() - INTERVAL '2 hours'")
    r2 = await conn.fetchrow("SELECT COUNT(DISTINCT source) FROM source_performance_log")
    print(f'\nS4 trust_log_this_run={r[0]}, unique_sources={r2[0]}')
    rows = await conn.fetch("SELECT DISTINCT ON (source) source, dynamic_trust_score, updated_at FROM source_performance_log ORDER BY source, updated_at DESC")
    for row in rows:
        print(f'    {row[0]}: trust={float(row[1]):.4f} @ {str(row[2])[:19]}')

    # S5: Paper trades
    r = await conn.fetchrow("SELECT COUNT(*) FROM paper_trades")
    print(f'\nS5 paper_trades_total={r[0]}')

    # Scout source tables
    print(f'\n  Scout source tables (this_run):')
    for tbl in ['market_regime_memory','liquidity_intelligence','correlation_memory','execution_intelligence']:
        try:
            r = await conn.fetchrow(f"SELECT COUNT(*), MAX(created_at) FROM {tbl} WHERE created_at > NOW() - INTERVAL '2 hours'")
            if r: print(f'    {tbl}: {r[0]} rows, latest={r[1]}')
        except: pass

    # S6: Event store / Audit
    r = await conn.fetchrow("SELECT COUNT(*) FROM event_store")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM audit_ledger")
    print(f'\nS6 event_store={r[0]}')
    print(f'   audit_ledger={r2[0]}')

    # Strategy statuses
    rows = await conn.fetch("SELECT status, COUNT(*) FROM strategies GROUP BY status")
    if rows:
        print(f'  Strategy statuses:')
        for row in rows: print(f'    {row[0]}: {row[1]}')

    # Check for strategy_generation_log
    try:
        r = await conn.fetchrow("SELECT COUNT(*) FROM strategy_generation_log WHERE created_at > NOW() - INTERVAL '2 hours'")
        print(f'\n  strategy_generation_log_this_run={r[0]}')
    except: pass

    # Check for model_generation_log (what Ideator uses)
    try:
        r = await conn.fetchrow("SELECT COUNT(*) FROM model_generation_log WHERE created_at > NOW() - INTERVAL '2 hours'")
        print(f'  model_generation_log_this_run={r[0]}')
    except: pass

    # Check all tables for any ideation activity
    try:
        r = await conn.fetchrow("""
            SELECT COUNT(*) FROM scout_influence_log 
            WHERE (target_agent ILIKE '%ideator%' OR influence_type ILIKE '%ideat%')
              AND created_at > NOW() - INTERVAL '2 hours'
        """)
        print(f'\n  Ideator-targeted influence events this_run={r[0]}')
    except: pass

    try:
        r = await conn.fetchrow("""
            SELECT COUNT(*) FROM scout_influence_log 
            WHERE influence_type ILIKE '%entropy%' OR influence_type ILIKE '%govern%'
              AND created_at > NOW() - INTERVAL '2 hours'
        """)
        print(f'  Entropy/governance influence events this_run={r[0]}')
    except: pass

    await conn.close()

asyncio.run(check())
