"""Quick test for the real PodcastScout RSS feed implementation."""

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent
sys.path.insert(0, str(_project_root))

from loguru import logger
from redis.asyncio import Redis
from atlas.agents.scouts.podcast_scout import PodcastScout, PODCAST_FEEDS
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    settings = get_settings()

    print("=" * 60)
    print("  PODCAST SCOUT RSS FEED TEST")
    print("=" * 60)
    print(f"  {len(PODCAST_FEEDS)} feeds configured:")
    for f in PODCAST_FEEDS:
        print(f"    - {f['name']}")

    print("\n  Connecting to DB and Redis...")
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)
    print("  [OK] Connected\n")

    # Run one cycle manually
    scout = PodcastScout(redis_client, db, run_interval=9999)
    await scout.start()

    print("  Testing RSS feed fetching and analysis...")
    await scout._gather_signals()

    await scout.stop()

    # Check results
    from sqlalchemy import text
    async with db.engine.connect() as conn:
        r = await conn.execute(
            text("SELECT source, COUNT(*) as cnt FROM external_scout_memory WHERE source = 'podcast' GROUP BY source")
        )
        row = r.fetchone()
        if row:
            print(f"\n  [OK] PodcastScout persisted {row[1]} signals to external_scout_memory")
        else:
            print("\n  [?] No podcast signals found (feeds may have no recent trading content)")

    await redis_client.aclose()
    await db.close()
    print("  [OK] Done\n")


if __name__ == "__main__":
    asyncio.run(main())
