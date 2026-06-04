"""Check the scout signal pipeline flow — scouts -> scout_signals -> external_scout_memory -> synthesis."""

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent
sys.path.insert(0, str(_project_root))

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy import text


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    async with db.engine.connect() as conn:
        print("=" * 70)
        print("  SCOUT SIGNAL PIPELINE FLOW")
        print("=" * 70)

        # 1. External scout memory (raw scout data from Discord, YouTube, etc.)
        r = await conn.execute(text("""
            SELECT source, COUNT(*) as cnt,
                   ROUND(AVG(sentiment)::numeric, 3) as avg_sentiment,
                   ROUND(AVG(hypothesis_score)::numeric, 3) as avg_score,
                   MAX(timestamp) as last_signal
            FROM external_scout_memory
            GROUP BY source
            ORDER BY cnt DESC
        """))
        print("\n[1] EXTERNAL SCOUT MEMORY (raw scout data):")
        print(f"  {'Source':<20s} {'Count':>8s} {'Avg Sent':>10s} {'Avg Score':>10s} 'Last Signal'")
        print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10} {'-'*25}")
        for row in r.fetchall():
            print(f"  {row[0]:<20s} {row[1]:>8d} {str(row[2]):>10s} {str(row[3]):>10s}  {str(row[4])[:25]}")

        # 2. Scout_signals (internal + mirrored)
        r = await conn.execute(text("""
            SELECT source, COUNT(*) as cnt,
                   ROUND(AVG(confidence_score)::numeric, 3) as avg_conf
            FROM scout_signals
            GROUP BY source
            ORDER BY cnt DESC
        """))
        print("\n[2] INTERNAL SCOUT SIGNALS (scout_signals table):")
        print(f"  {'Source':<20s} {'Count':>8s} {'Avg Confidence':>15s}")
        print(f"  {'-'*20} {'-'*8} {'-'*15}")
        for row in r.fetchall():
            print(f"  {row[0]:<20s} {row[1]:>8d} {str(row[2]):>15s}")

        # 3. Scout synthesis log (ScoutSynthesisEngine output)
        r = await conn.execute(text("""
            SELECT id, confidence, scout_agreement_score,
                   contextual_summary, market_state_interpretation,
                   created_at
            FROM scout_synthesis_log
            ORDER BY created_at DESC
            LIMIT 3
        """))
        print("\n[3] SCOUT SYNTHESIS LOG (ScoutSynthesisEngine outputs):")
        rows = r.fetchall()
        if rows:
            for row in rows:
                print(f"  ID: {str(row[0])[:20]}")
                print(f"  Confidence: {row[1]:.2f} | Agreement: {row[2]:.2f}")
                summary = str(row[3])[:120] if row[3] else "(empty)"
                print(f"  Summary: {summary}")
                interp = str(row[4])[:80] if row[4] else "(empty)"
                print(f"  Interpretation: {interp}")
                print(f"  Created: {str(row[5])[:25]}")
                print()
        else:
            print("  (no synthesis entries yet)")

        # 4. Latest external scout signals detail
        r = await conn.execute(text("""
            SELECT source, source_sub, hypothesis_score, signal_direction,
                   sentiment, timestamp
            FROM external_scout_memory
            WHERE timestamp > NOW() - INTERVAL '7 days'
            ORDER BY timestamp DESC
            LIMIT 5
        """))
        print("\n[4] LATEST EXTERNAL SCOUT SIGNALS (last 7 days):")
        rows = r.fetchall()
        if rows:
            for row in rows:
                print(f"  [{row[0]}] {row[1]} | score={row[2]:.2f} dir={row[3]} sent={row[4]:.2f} @ {str(row[5])[:19]}")
        else:
            print("  (no recent signals)")

        # 5. Pipeline summary counts
        r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
        ext_total = r.scalar() or 0
        r = await conn.execute(text("SELECT COUNT(*) FROM scout_signals"))
        sig_total = r.scalar() or 0
        r = await conn.execute(text("SELECT COUNT(*) FROM scout_synthesis_log"))
        synth_total = r.scalar() or 0

        print()
        print("=" * 70)
        print("  PIPELINE FLOW SUMMARY")
        print("=" * 70)
        print(f"  External Scouts (raw):      {ext_total:>6} signals")
        print(f"  Scout Signals (mirrored):   {sig_total:>6} signals")
        print(f"  Scout Synthesis (engine):   {synth_total:>6} outputs")
        print()
        print("  Flow: [Discord/YouTube/Reddit/etc] -> external_scout_memory")
        print("                                            |")
        print("                       ScoutSynthesisEngine -+-> scout_synthesis_log")
        print("                                            |")
        print("                       AntiPoisoningEngine  -+-> scout_quarantine")
        print("                                            |")
        print("                       Ideator              -+-> strategies -> backtests")
        print("=" * 70)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
