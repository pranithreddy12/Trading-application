"""
test_external_scouts.py — Full smoke test for all external scouts.

Starts Discord (real-time gateway), YouTube (Data API), and Podcast (RSS feeds)
with short run intervals, lets them run, then checks persistence.
"""

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
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

    print("=" * 70)
    print("  FULL SCOUT NETWORK SMOKE TEST")
    print("=" * 70)

    # Count before
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
        before_ext = r.scalar() or 0
        r = await conn.execute(text("SELECT COUNT(*) FROM scout_signals"))
        before_sig = r.scalar() or 0
        r = await conn.execute(
            text("SELECT source, COUNT(*) FROM external_scout_memory GROUP BY source ORDER BY source")
        )
        before_sources = {row[0]: row[1] for row in r.fetchall()}

    print(f"\n  BEFORE - external_scout_memory: {before_ext} rows")
    for src, cnt in sorted(before_sources.items()):
        print(f"    {src}: {cnt}")
    print(f"  BEFORE - scout_signals: {before_sig} rows")

    # Build scouts
    scouts = []
    scouts.append(DiscordScout(redis_client, db))
    scouts.append(YouTubeScout(redis_client, db, run_interval=15))
    scouts.append(PodcastScout(redis_client, db, run_interval=30))

    # Start
    print("\n  Starting scouts...")
    for s in scouts:
        await s.start()
        print(f"  [STARTED] {s.name}")

    # Wait for Discord gateway
    discord_scout = next(s for s in scouts if isinstance(s, DiscordScout))
    print("\n  Waiting for Discord gateway (up to 15s)...")
    try:
        await asyncio.wait_for(discord_scout._gateway_connected.wait(), timeout=15)
        print("  [OK] Discord gateway connected!")
    except asyncio.TimeoutError:
        print("  [WARN] Discord gateway timeout (non-fatal)")

    # Run for 75 seconds (YouTube polls at 15s, Podcast at 30s)
    print("\n  Running scouts for 75 seconds...")
    await asyncio.sleep(75)

    # Stop
    print("\n  Stopping scouts...")
    for s in reversed(scouts):
        await s.stop()
        print(f"  [STOPPED] {s.name}")

    # Count after
    async with db.engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
        after_ext = r.scalar() or 0
        r = await conn.execute(text("SELECT COUNT(*) FROM scout_signals"))
        after_sig = r.scalar() or 0
        r = await conn.execute(
            text("SELECT source, COUNT(*) FROM external_scout_memory GROUP BY source ORDER BY source")
        )
        after_sources = {row[0]: row[1] for row in r.fetchall()}

    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(f"\n  BEFORE -> AFTER")
    print(f"  external_scout_memory: {before_ext} -> {after_ext} ({after_ext - before_ext:+d})")
    print(f"  scout_signals:         {before_sig} -> {after_sig} ({after_sig - before_sig:+d})")

    print("\n  By source (external_scout_memory):")
    for src in sorted(set(list(before_sources.keys()) + list(after_sources.keys()))):
        b = before_sources.get(src, 0)
        a = after_sources.get(src, 0)
        delta = a - b
        status = "NEW" if b == 0 and a > 0 else ("+" if delta > 0 else "=")
        print(f"    {src:<15s}  {b:>5d} -> {a:>5d}  ({delta:+d}) [{status}]")

    print("\n" + "=" * 70)
    if after_ext > before_ext:
        print("  RESULT: Scouts are working - new data persisted!")
    else:
        print("  RESULT: No new data (feeds may have no recent trading content)")
    print("=" * 70 + "\n")

    await redis_client.aclose()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
