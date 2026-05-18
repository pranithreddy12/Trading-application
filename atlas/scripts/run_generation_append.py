"""
run_generation_append.py
Run IdeatorAgentV2 (5 instances) + CoderAgent for 50 cycles to generate 150+ strategies.
All strategies appended to DB — no overwrites.

Usage:
    python atlas/scripts/run_generation_append.py
"""
import asyncio
from loguru import logger
from redis.asyncio import Redis

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2, ARCHETYPES
from atlas.agents.l2_strategy.strategy_normalizer import (
    normalize_strategy,
    compute_strategy_signature,
)


async def run_single_ideation(
    ideator: IdeatorAgentV2, db: TimescaleClient, cycle: int
) -> int:
    """Run one ideation + save cycle. Returns number of strategies saved."""
    saved = 0
    try:
        # Refresh context every 10 cycles (matches internal cache TTL)
        if cycle % 10 == 0:
            ideator._ctx_cache = await ideator._build_context()
        ideator._ctx_cycle = cycle

        spec, prompt, raw = await ideator._generate(ideator._ctx_cache)
        if not spec:
            return 0

        sig = compute_strategy_signature(spec)
        existing_sigs = await db.get_strategy_signatures(limit=1000)
        if sig in existing_sigs:
            logger.debug(f"{ideator.name}: Duplicate — skipped")
            return 0

        strategy_id = await db.save_strategy(
            spec,
            status="pending_code",
            author_agent=ideator.name,
            prompt=prompt,
            raw_response=raw,
            strategy_signature=sig,
        )
        logger.info(f"{ideator.name}: ✅ Saved [{spec['strategy_name']}] id={strategy_id}")
        saved += 1

    except Exception as e:
        logger.warning(f"{ideator.name}: cycle {cycle} error: {e}")

    return saved


async def main():
    db = TimescaleClient(db_url=settings.database_url)
    await db.connect()
    redis = Redis.from_url(settings.redis_url)

    # 5 ideator instances: 2 rich, 2 lean, 1 local (matches standard pipeline)
    ideators = [
        IdeatorAgentV2(0, 0.5, redis, db, mode="rich"),
        IdeatorAgentV2(1, 0.7, redis, db, mode="rich"),
        IdeatorAgentV2(2, 0.4, redis, db, mode="lean"),
        IdeatorAgentV2(3, 0.85, redis, db, mode="lean"),
        IdeatorAgentV2(4, 0.0, redis, db, mode="local"),
    ]
    # Pre-load context for all ideators
    for ideator in ideators:
        ideator._ctx_cache = await ideator._build_context()

    print("Starting append-only generation run...", flush=True)
    total_saved = 0

    for i in range(50):  # 50 cycles × 5 ideators = up to 250 attempts → 150+ unique
        print(f"Cycle {i + 1}/50", flush=True)
        results = await asyncio.gather(
            *[run_single_ideation(idtr, db, i) for idtr in ideators],
            return_exceptions=True,
        )
        cycle_saved = sum(r for r in results if isinstance(r, int))
        total_saved += cycle_saved
        logger.info(f"Cycle {i + 1}: +{cycle_saved} strategies (total={total_saved})")
        await asyncio.sleep(2)  # brief pause between cycles to avoid Claude rate-limiting

    # Trigger CoderAgent to process all pending_code strategies
    from atlas.agents.l2_strategy.coder_agent import CoderAgent
    coder = CoderAgent(redis_client=redis, db_client=db)
    pending = await db.get_strategies_by_status("pending_code")
    logger.info(f"Coding {len(pending)} pending strategies...")
    for strategy in pending:
        await coder._code_strategy(strategy)

    print(f"\nDone. Total strategies generated: {total_saved}", flush=True)
    pending_after = await db.get_strategies_by_status("pending_backtest")
    print(f"Strategies ready for backtest: {len(pending_after)}", flush=True)

    await redis.aclose()
    await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
