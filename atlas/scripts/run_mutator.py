"""
Standalone launcher for MutatorAgent v2.

Usage:
    python scripts/run_mutator.py
    python scripts/run_mutator.py --interval 30 --min-entries 1 --min-trades 1

Environment:
    Requires ATLAS config (redis_url, database_url) in atlas/config/.env or environment.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger
from redis.asyncio import Redis

from atlas.agents.l2_strategy.mutator_agent import (
    MutatorAgent,
    MIN_ENTRY_COUNT,
    MIN_TRADES,
)
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    parser = argparse.ArgumentParser(description="MutatorAgent v2 Launcher")
    parser.add_argument(
        "--interval",
        type=int,
        default=900,
        help="Cycle interval in seconds (default 900)",
    )
    parser.add_argument(
        "--min-entries",
        type=int,
        default=None,
        help="Override MIN_ENTRY_COUNT (default 3)",
    )
    parser.add_argument(
        "--min-trades", type=int, default=None, help="Override MIN_TRADES (default 3)"
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=10,
        help="Max repair candidates per cycle (default 10)",
    )
    args = parser.parse_args()

    if args.min_entries is not None:
        import atlas.agents.l2_strategy.mutator_agent as ma

        ma.MIN_ENTRY_COUNT = args.min_entries
        logger.info(f"Overriding MIN_ENTRY_COUNT → {args.min_entries}")

    if args.min_trades is not None:
        import atlas.agents.l2_strategy.mutator_agent as ma

        ma.MIN_TRADES = args.min_trades
        logger.info(f"Overriding MIN_TRADES → {args.min_trades}")

    logger.info("=" * 60)
    logger.info("  MutatorAgent v2 — Standalone Launcher")
    logger.info(f"  Redis:    {settings.redis_url}")
    logger.info(f"  Database: {settings.database_url}")
    logger.info(f"  Interval: {args.interval}s")
    logger.info(f"  Candidates/cycle: {args.candidates}")
    logger.info("=" * 60)

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    db_client = TimescaleClient(db_url=settings.database_url)
    await db_client.connect()

    agent = MutatorAgent(redis_client=redis_client, db_client=db_client)
    agent.RUN_INTERVAL_SECONDS = args.interval
    agent.status = "running"
    logger.info(f"MutatorAgent status: {agent.status}")

    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await redis_client.close()
        logger.info("Redis connection closed")


if __name__ == "__main__":
    asyncio.run(main())
