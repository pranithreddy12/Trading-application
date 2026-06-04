"""
soak_scouts_30min.py — 30-minute soak for all external scouts.

Runs Discord (real-time), YouTube (every 5min), Podcast (every 10min)
for 30 minutes, then reports how much real data was accumulated.
"""

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent
sys.path.insert(0, str(_project_root))

from loguru import logger
from redis.asyncio import Redis

from atlas.agents.scouts.discord_scout import DiscordScout
from atlas.agents.scouts.youtube_scout import YouTubeScout
from atlas.agents.scouts.podcast_scout import PodcastScout
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from sqlalchemy import text


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    print("=" * 70)
    print("  30-MINUTE SCOUT SOAK")
    print("=" * 70)
    print("  Starting with a clean database (all old data already deleted)")
    print()

    # Instantiate scouts with shorter intervals for the soak
    scouts = [
        DiscordScout(redis_client, db),              # real-time gateway
        YouTubeScout(redis_client, db, run_interval=300),   # every 5 min
        PodcastScout(redis_client, db, run_interval=600),   # every 10 min
    ]

    # Start all scouts
    print("  Starting scouts...")
    for s in scouts:
        await s.start()
        print(f"  [STARTED] {s.name}")

    # Wait for Discord gateway
    discord_scout = next(s for s in scouts if isinstance(s, DiscordScout))
    print("\n  Waiting for Discord gateway (up to 20s)...")
    try:
        await asyncio.wait_for(discord_scout._gateway_connected.wait(), timeout=20)
        print("  [OK] Discord gateway connected!")
    except asyncio.TimeoutError:
        print("  [WARN] Discord gateway timeout")

    # Run for 30 minutes with progress updates
    print("\n  Soaking for 30 minutes...")
    print("  Discord: listening for live messages")
    print("  YouTube: searching every 5 minutes")
    print("  Podcast: scanning RSS feeds every 10 minutes")
    print()

    for minute in range(1, 31):
        await asyncio.sleep(60)
        # Show progress
        async with db.engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
            total = r.scalar() or 0
            r = await conn.execute(
                text("SELECT source, COUNT(*) FROM external_scout_memory GROUP BY source ORDER BY source")
            )
            sources = {row[0]: row[1] for row in r.fetchall()}
        source_str = ", ".join(f"{k}={v}" for k, v in sorted(sources.items())) or "none"
        print(f"  t={minute:2d}min  |  total={total:>4d}  ({source_str})")

    # Stop all scouts
    print("\n  Stopping scouts...")
    for s in reversed(scouts):
        await s.stop()
        print(f"  [STOPPED] {s.name}")

    # Final report
    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
        total = r.scalar() or 0
        r = await conn.execute(
            text("SELECT source, COUNT(*) FROM external_scout_memory GROUP BY source ORDER BY source")
        )
        rows = r.fetchall()

        print(f"\n  Total signals: {total}")
        if rows:
            for row in rows:
                print(f"    {row[0]:<15s} {row[1]:>5d} signals")
        else:
            print("    (no signals collected - try running longer)")

        # Show latest 5 signals
        if total > 0:
            r = await conn.execute(
                text("""
                SELECT source, source_sub, hypothesis_score, signal_direction,
                       sentiment, timestamp
                FROM external_scout_memory
                ORDER BY timestamp DESC LIMIT 5
                """)
            )
            print("\n  Latest signals:")
            for row in r.fetchall():
                print(f"    [{row[0]}] {row[1]} | score={row[2]:.2f} dir={row[3]} sent={row[4]:.2f}")
        else:
            print("\n  No signals collected this run.")
            print("  Tip: Send messages in your Discord trading channel during the soak to trigger the DiscordScout.")

    print("=" * 70 + "\n")

    await redis_client.aclose()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
