"""P6 T7 — Batch execution command for the shadow computation pipeline.

Computes ledger_metrics_v1 / research_fitness / deploy_fitness / validator status
for an explicit set of strategies (or a --limit sample) and writes ONLY to the
*_v1 shadow tables. Touches no legacy surface.

Usage:
  python -m atlas.scripts.run_shadow_pipeline --limit 50 [--ensure-tables]
  python -m atlas.scripts.run_shadow_pipeline --strategy-id <uuid> [--strategy-id <uuid> ...]
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
    ap = argparse.ArgumentParser(description="Run the v1 shadow computation pipeline (batch).")
    ap.add_argument("--limit", type=int, default=None, help="process at most N strategies (sample)")
    ap.add_argument("--strategy-id", action="append", default=None, help="explicit strategy id (repeatable)")
    ap.add_argument("--ensure-tables", action="store_true", help="create the *_v1 tables first (idempotent)")
    args = ap.parse_args()

    db = TimescaleClient(settings.database_url)
    await db.connect()
    if args.ensure_tables:
        await db.ensure_v1_tables()
        logger.info("ensured v1 shadow tables exist")

    pipe = ShadowComputationPipeline(db)

    t0 = time.perf_counter()
    if args.strategy_id:
        summary = await pipe.run_batch(args.strategy_id)
        summary["population_size"] = len(args.strategy_id)
    else:
        ids = await db.get_strategy_ids_with_backtest_results(limit=args.limit)
        summary = await pipe.run_batch(ids)
        summary["population_size"] = len(ids)
    elapsed = time.perf_counter() - t0

    summary["elapsed_sec"] = round(elapsed, 2)
    summary["throughput_per_sec"] = (
        round(summary["processed"] / elapsed, 2) if elapsed > 0 else None
    )
    logger.info("SHADOW PIPELINE (batch) COMPLETE\n" + json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
