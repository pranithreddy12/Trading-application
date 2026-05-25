"""Phase 27 DB diagnostic check."""
import asyncio
import sys
import os
# Add parent dir so atlas package resolves correctly
PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy.sql import text


async def main():
    s = get_settings()
    db = TimescaleClient(s.database_url)
    await db.connect()

    async with db.engine.connect() as conn:
        # Strategy counts by status
        r = await conn.execute(text(
            "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY COUNT(*) DESC"
        ))
        print("=== STRATEGY STATUS BREAKDOWN ===")
        rows = r.fetchall()
        if not rows:
            print("  (no strategies)")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")

        # Recent 24h
        r2 = await conn.execute(text(
            "SELECT COUNT(*) FROM strategies WHERE created_at > NOW() - INTERVAL '24 hours'"
        ))
        print(f"\nStrategies in last 24h: {r2.fetchone()[0]}")

        # Active diversity anchors
        r3 = await conn.execute(text(
            "SELECT COUNT(*) FROM strategies "
            "WHERE normalized_strategy IS NOT NULL "
            "AND (status NOT IN ('code_failed','permanently_failed','invalidated','obsolete') OR status IS NULL) "
            "AND created_at > NOW() - INTERVAL '7 days'"
        ))
        print(f"Active diversity anchors (7d, non-failed): {r3.fetchone()[0]}")

        # Scout influence logs
        try:
            r4 = await conn.execute(text(
                "SELECT COUNT(*) FROM scout_influence_log WHERE created_at > NOW() - INTERVAL '24 hours'"
            ))
            print(f"Scout influence events (24h): {r4.fetchone()[0]}")
        except Exception as e:
            print(f"Scout influence log: {e}")

        # Trust scores
        try:
            r5 = await conn.execute(text(
                "SELECT source, dynamic_trust_score, updated_at FROM source_performance_log "
                "ORDER BY updated_at DESC LIMIT 15"
            ))
            print("\n=== TRUST SCORES (latest per source) ===")
            rows5 = r5.fetchall()
            if not rows5:
                print("  (no trust records)")
            for row in rows5:
                print(f"  {row[0]}: {row[1]:.3f} (updated: {row[2]})")
        except Exception as e:
            print(f"Trust scores error: {e}")

        # Economic attribution
        try:
            r6 = await conn.execute(text(
                "SELECT COUNT(*) FROM scout_economic_attribution WHERE created_at > NOW() - INTERVAL '24 hours'"
            ))
            print(f"\nEconomic attribution events (24h): {r6.fetchone()[0]}")
        except Exception as e:
            print(f"Economic attribution: {e}")

        # GC check: stale code_failed
        try:
            r7 = await conn.execute(text(
                "SELECT COUNT(*) FROM strategies WHERE status = 'code_failed' "
                "AND created_at < NOW() - INTERVAL '24 hours'"
            ))
            print(f"\nStale code_failed strategies (>24h old): {r7.fetchone()[0]}")
        except Exception as e:
            print(f"GC check: {e}")

    await db.close()
    print("\nDiagnostic complete.")


if __name__ == "__main__":
    asyncio.run(main())
