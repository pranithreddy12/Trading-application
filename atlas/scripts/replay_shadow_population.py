"""P6 T7 — Replay command for the historical population.

Replays the shadow computation pipeline over the ENTIRE population (every strategy
with a backtest_results row), writing only to the *_v1 shadow tables. Idempotent
(upserts), so it can be re-run safely. Touches no legacy surface.

Usage:
  python -m atlas.scripts.replay_shadow_population [--ensure-tables] [--limit N]
"""
import argparse
import asyncio
import json
import time

from loguru import logger

from atlas.config.settings import settings
from atlas.core.shadow_pipeline import ShadowComputationPipeline
from atlas.data.storage.timescale_client import TimescaleClient


async def main() -> None:
    ap = argparse.ArgumentParser(description="Replay the v1 shadow pipeline over the full population.")
    ap.add_argument("--ensure-tables", action="store_true", help="create the *_v1 tables first (idempotent)")
    ap.add_argument("--limit", type=int, default=None, help="cap population size (default: all)")
    ap.add_argument("--resume", action="store_true", help="skip strategies already in validator_results_v1")
    ap.add_argument("--progress-every", type=int, default=50, help="log running totals every N strategies")
    args = ap.parse_args()

    db = TimescaleClient(settings.database_url)
    await db.connect()
    if args.ensure_tables:
        await db.ensure_v1_tables()
        logger.info("ensured v1 shadow tables exist")

    pipe = ShadowComputationPipeline(db)

    def _progress(snap: dict) -> None:
        logger.info(
            f"progress: processed={snap['processed']} written={snap['written']} "
            f"skipped={snap['skipped']} failed={snap['failed']}"
        )

    t0 = time.perf_counter()
    summary = await pipe.replay_population(
        limit=args.limit,
        resume=args.resume,
        progress_every=args.progress_every,
        progress_cb=_progress,
    )
    elapsed = time.perf_counter() - t0

    summary["elapsed_sec"] = round(elapsed, 2)
    summary["throughput_per_sec"] = (
        round(summary["processed"] / elapsed, 2) if elapsed > 0 else None
    )
    logger.info("SHADOW PIPELINE (replay) COMPLETE\n" + json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
