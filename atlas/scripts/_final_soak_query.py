"""Phase 26H — Final Soak Results Query."""
import asyncio, re
from atlas.config.settings import settings
import asyncpg

async def check():
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    conn = await asyncpg.connect(db_url)

    print('=== FINAL PHASE 26H SOAK RESULTS ===')
    print(f'Report time: {await conn.fetchval("SELECT NOW()")}\n')

    # ── S1: Scout Signals ──
    r2 = await conn.fetchrow("SELECT COUNT(*), MAX(created_at) FROM scout_signals")
    r3 = await conn.fetchrow("SELECT COUNT(*) FROM scout_signals WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'S1 scout_signals total: {r2[0]}, this run: {r3[0]}, latest: {r2[1]}')

    rows = await conn.fetch("SELECT source, COUNT(*) as cnt FROM scout_signals WHERE created_at > NOW() - INTERVAL '2 hours' GROUP BY source ORDER BY cnt DESC")
    print(f'  sources ({len(rows)}):')
    for r in rows:
        print(f'    {r[0]}: {r[1]}')

    # ── S2: Strategies ──
    r = await conn.fetchrow("SELECT COUNT(*), MAX(created_at) FROM strategies")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM strategies WHERE created_at > NOW() - INTERVAL '2 hours'")
    r3 = await conn.fetchrow("SELECT COUNT(*) FROM backtest_results WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'\nS2 strategies total: {r[0]}, this run: {r2[0]}, latest: {r[1]}')
    print(f'  backtest_results this run: {r3[0]}')

    if r3[0] > 0:
        rows = await conn.fetch("""
            SELECT b.strategy_id, b.sharpe, b.sortino_ratio, b.win_rate, b.max_drawdown, b.created_at
            FROM backtest_results b
            WHERE b.created_at > NOW() - INTERVAL '2 hours'
            ORDER BY b.sharpe DESC LIMIT 5
        """)
        print('  Top backtests:')
        for row in rows:
            print(f'    {row[0]}: sharpe={float(row[1]):.3f}, sortino={float(row[2]):.3f}, win_rate={float(row[3]):.3f}, max_dd={float(row[4]):.3f}')

    # ── S3: Scout Influence ──
    r = await conn.fetchrow("SELECT COUNT(*) FROM scout_influence_log WHERE created_at > NOW() - INTERVAL '2 hours'")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution")
    r3 = await conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'\nS3 scout_influence_log (this run): {r[0]}')
    print(f'  scout_economic_attribution total: {r2[0]}, this run: {r3[0]}')

    if r[0] > 0:
        rows = await conn.fetch("""
            SELECT source_scout, target_agent, influence_type, influence_metric, delta, created_at
            FROM scout_influence_log
            WHERE created_at > NOW() - INTERVAL '2 hours'
            ORDER BY created_at DESC LIMIT 15
        """)
        print('  Influence events:')
        for row in rows:
            print(f'    {row[0]} -> {row[1]}: {row[2]}({row[3]}) delta={float(row[4]):.4f} @ {str(row[5])[:19]}')

    # ── S4: Trust Evolution ──
    r = await conn.fetchrow("SELECT COUNT(*) FROM source_performance_log WHERE updated_at > NOW() - INTERVAL '2 hours'")
    r2 = await conn.fetchrow("SELECT COUNT(DISTINCT source) FROM source_performance_log")
    print(f'\nS4 trust_log (this run): {r[0]}, unique sources: {r2[0]}')

    rows = await conn.fetch("SELECT source, dynamic_trust_score, updated_at FROM source_performance_log ORDER BY updated_at DESC LIMIT 10")
    if rows:
        print('  Latest trust scores:')
        for row in rows:
            print(f'    {row[0]}: {float(row[1]):.4f} @ {str(row[2])[:19]}')

    # ── S5: Execution ──
    r = await conn.fetchrow("SELECT COUNT(*) FROM paper_trades")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM paper_trades WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'\nS5 paper_trades total: {r[0]}, this run: {r2[0]}')

    r = await conn.fetchrow("SELECT COUNT(*) FROM mutation_record WHERE created_at > NOW() - INTERVAL '2 hours'")
    print(f'  mutation_record (this run): {r[0]}')

    # ── S6: Replay/Audit ──
    r = await conn.fetchrow("SELECT COUNT(*) FROM event_store")
    r2 = await conn.fetchrow("SELECT COUNT(*) FROM audit_ledger")
    print(f'\nS6 event_store: {r[0]} rows')
    print(f'   audit_ledger: {r2[0]} rows')

    # ── Scout source tables ──
    for tbl in ['market_regime_memory', 'liquidity_intelligence', 'correlation_memory', 'execution_intelligence']:
        r = await conn.fetchrow(f"SELECT COUNT(*), MAX(created_at) FROM {tbl}")
        if r:
            print(f'  {tbl}: {r[0]} rows, latest={r[1]}')

    # ── Strategy statuses ──
    rows = await conn.fetch("SELECT status, COUNT(*) FROM strategies GROUP BY status")
    if rows:
        print(f'\n  Strategy statuses:')
        for row in rows:
            print(f'    {row[0]}: {row[1]}')

    await conn.close()

asyncio.run(check())
