"""
Phase 27 pre-soak DB cleanup.
Runs evolutionary garbage collection + resets stale trust scores.
"""

import asyncio
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

from atlas.config.settings import settings
import asyncpg


async def run():
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    conn = await asyncpg.connect(db_url)

    print("=" * 60)
    print("PHASE 27 PRE-SOAK DB CLEANUP")
    print("=" * 60)

    # Step 1: Count current state
    print("\n[1/4] Counting current DB state...")
    for table in ['strategies', 'scout_signals', 'scout_influence_log',
                  'scout_economic_attribution', 'source_performance_log',
                  'mutation_record']:
        try:
            r = await conn.fetchrow(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table}: {r[0]}")
        except Exception as e:
            print(f"  {table}: ERROR ({e})")

    # Step 2: Run evolutionary GC
    print("\n[2/4] Running evolutionary garbage collection...")
    try:
        from data.storage.timescale_client import TimescaleClient
        from atlas.config.settings import settings as s
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(s.database_url)
        db = TimescaleClient.__new__(TimescaleClient)
        db.engine = engine
        gc_result = await db.evolutionary_garbage_collection(dry_run=True)
        print(f"  GC result: {json.dumps(gc_result)}")

        if any(v > 0 for v in gc_result.values()):
            print("  Executing GC with dry_run=False...")
            actual = await db.evolutionary_garbage_collection(dry_run=False)
            print(f"  Actual rows affected: {json.dumps(actual)}")
        else:
            print("  No stale data to clean.")
        await engine.dispose()
    except Exception as e:
        print(f"  GC skipped: {e}")

    # Step 3: Reset stale trust scores
    print("\n[3/4] Resetting stale trust scores...")
    try:
        stale = await conn.fetch(
            "SELECT source, source_sub, dynamic_trust_score FROM source_performance_log "
            "WHERE updated_at < NOW() - INTERVAL '24 hours'"
        )
        print(f"  Stale trust entries: {len(stale)}")
        for s in stale:
            print(f"    {s[0]}/{s[1]}: trust={s[2]} (stale)")
            await conn.execute(
                "DELETE FROM source_performance_log WHERE source=$1 AND source_sub=$2",
                s[0], s[1]
            )

        # Insert fresh trust entries for active scouts
        active_sources = [
            ('regime_scout', 'regime_detection', 0.5),
            ('liquidity_scout', 'liquidity_assessment', 0.5),
            ('correlation_scout', 'correlation_detection', 0.5),
            ('news_scout', 'news_intelligence', 0.5),
            ('source_reliability', 'source_trust', 0.5),
        ]
        for source, sub, trust in active_sources:
            await conn.execute("""
                INSERT INTO source_performance_log
                    (id, source, source_sub, dynamic_trust_score,
                     historical_accuracy, n_profitable_signals,
                     n_loss_signals, updated_at)
                VALUES
                    ($1, $2, $3, $4, 0.5, 0, 0, NOW())
                ON CONFLICT (id) DO UPDATE
                    SET dynamic_trust_score = $4,
                        historical_accuracy = 0.5,
                        updated_at = NOW()
            """, f"{source}_{sub}_fresh", source, sub, trust)
            print(f"    {source}/{sub}: trust reset to {trust}")
    except Exception as e:
        print(f"  Trust reset skipped: {e}")

    # Step 4: Verify final state
    print("\n[4/4] Final state...")
    for table in ['strategies', 'scout_signals', 'scout_influence_log',
                  'source_performance_log']:
        try:
            r = await conn.fetchrow(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table}: {r[0]}")
        except Exception as e:
            print(f"  {table}: ERROR ({e})")

    await conn.close()
    print("\nDone. Ready for Phase 27G soak.")

asyncio.run(run())
