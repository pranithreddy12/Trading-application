"""
run_overnight_generation.py — Continuous pipeline loop for overnight generation.

Runs the full Ideator → Coder → Backtest → Validate cycle continuously.
When the pipeline empties (all strategies fail validation), it triggers a new
generation cycle so the loop never stalls.

Usage:
    python atlas/scripts/run_overnight_generation.py [--duration-minutes N]

Default duration: 480 minutes (8 hours).
"""

import asyncio
import argparse
import time
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2
from atlas.agents.l2_strategy.coder_agent import CoderAgent
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent
from atlas.agents.l2_strategy.ideator_agent_v2 import compute_strategy_signature


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
IDEATOR_INSTANCES = 3          # parallel ideator workers
IDEATOR_TEMPERATURES = [0.5, 0.7, 0.9]
POLL_INTERVAL_SECONDS = 15     # seconds between pipeline-empty checks
REFILL_EVERY_N_CYCLES = 3      # trigger generation every N empty cycles
STATUS_REPORT_INTERVAL = 1800  # log a status table every 30 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def status_report(db: TimescaleClient) -> None:
    """Print a live strategy status breakdown."""
    try:
        async with db.engine.connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC")
                )
            ).fetchall()
            distinct = (
                await conn.execute(text("SELECT COUNT(DISTINCT name) FROM strategies"))
            ).scalar()
        logger.info("=" * 60)
        logger.info("PIPELINE STATUS SNAPSHOT")
        logger.info(f"  Distinct strategy names: {distinct}")
        for r in rows:
            logger.info(f"  {r[0]:<28} {r[1]}")
        logger.info("=" * 60)
    except Exception as e:
        logger.warning(f"Status report failed: {e}")


async def trigger_generation_cycle(
    ideator: IdeatorAgentV2,
    coder: CoderAgent,
    db: TimescaleClient,
) -> int:
    """
    Run one mini generation batch: build context, generate up to 3 specs,
    code them, and hand them off to pending_backtest.
    Returns the number of strategies injected.
    """
    injected = 0
    try:
        ctx = await ideator._build_context()
        existing_sigs = await db.get_strategy_signatures(limit=500)

        for _ in range(3):  # generate up to 3 per refill
            try:
                spec, prompt, raw = await ideator._generate(ctx)
                if not spec:
                    continue

                sig = compute_strategy_signature(spec)
                if sig in existing_sigs:
                    logger.info("Refill: duplicate signature — skip")
                    continue

                strategy_id = await db.save_strategy(
                    spec,
                    status="pending_code",
                    author_agent="PipelineRefill",
                    prompt=prompt,
                    raw_response=raw,
                    strategy_signature=sig,
                )
                existing_sigs.add(sig)
                logger.info(
                    f"Refill: generated '{spec.get('strategy_name', 'unknown')}' "
                    f"(id={strategy_id})"
                )

                # Immediately code it so it flows into pending_backtest
                strategies = await db.get_strategies_by_status("pending_code")
                for s in strategies:
                    if s["id"] == strategy_id:
                        await coder._code_strategy(s)
                        injected += 1
                        break

            except Exception as e:
                logger.warning(f"Refill generation error: {e}")

    except Exception as e:
        logger.error(f"Refill cycle failed: {e}")

    return injected


async def pipeline_loop(
    db: TimescaleClient,
    redis_client: Redis,
    ideators: list[IdeatorAgentV2],
    coder: CoderAgent,
    runner: BacktestRunner,
    validator: ValidatorAgent,
    end_time: float,
) -> None:
    """
    Main continuous pipeline loop.
    - Drains pending_backtest → backtest → validate
    - When empty, triggers refill via IdeatorAgentV2
    - Logs status every 30 minutes
    """
    empty_cycles = 0
    last_status_report = time.time()
    primary_ideator = ideators[0]  # use instance 0 for refill triggers

    while time.time() < end_time:
        # ── Status report every 30 min ─────────────────────────────────────
        if time.time() - last_status_report >= STATUS_REPORT_INTERVAL:
            await status_report(db)
            last_status_report = time.time()

        # ── Check pending_backtest ─────────────────────────────────────────
        try:
            pending_bt = await db.get_strategies_by_status("pending_backtest")
        except Exception as e:
            logger.error(f"DB poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        if not pending_bt:
            empty_cycles += 1
            logger.info(
                f"Pipeline empty (empty_cycle={empty_cycles}) — "
                f"waiting for ideators or triggering refill"
            )

            # Every N empty cycles, explicitly trigger a mini generation batch
            if empty_cycles % REFILL_EVERY_N_CYCLES == 0:
                logger.info("Triggering forced refill generation cycle...")
                injected = await trigger_generation_cycle(
                    primary_ideator, coder, db
                )
                logger.info(f"Refill complete: {injected} strategies injected")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        # ── Reset empty counter — pipeline has work ────────────────────────
        empty_cycles = 0

        # ── Backtest ───────────────────────────────────────────────────────
        logger.info(f"Backtesting {len(pending_bt)} strategies...")
        for s in pending_bt:
            name = s.get("name", s.get("id", "?"))
            try:
                await runner.process_strategy(s)
            except Exception as e:
                logger.error(f"Backtest failed [{name}]: {type(e).__name__}: {e}")

        # ── Validate ───────────────────────────────────────────────────────
        try:
            pending_val = await db.get_strategies_by_status("pending_validation")
        except Exception:
            pending_val = []

        if pending_val:
            logger.info(f"Validating {len(pending_val)} strategies...")
            for s in pending_val:
                sid = s["id"]
                name = s.get("name", sid)
                try:
                    await validator._validate_one(sid, name)
                except Exception as e:
                    logger.error(f"Validation failed [{name}]: {type(e).__name__}: {e}")

        # ── Also drain any pending_code that ideators have left ────────────
        try:
            pending_code = await db.get_strategies_by_status("pending_code")
        except Exception:
            pending_code = []

        if pending_code:
            logger.info(f"Coding {len(pending_code)} strategies...")
            for s in pending_code:
                name = s.get("name", s.get("id", "?"))
                try:
                    await coder._code_strategy(s)
                except Exception as e:
                    logger.error(f"Coder failed [{name}]: {type(e).__name__}: {e}")

        # brief pause between full cycles
        await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(duration_minutes: int) -> None:
    end_time = time.time() + duration_minutes * 60
    logger.info(f"Starting overnight generation — duration={duration_minutes}m")

    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    # Instantiate agents
    ideators = [
        IdeatorAgentV2(
            instance_id=i,
            temperature=IDEATOR_TEMPERATURES[i % len(IDEATOR_TEMPERATURES)],
            redis_client=redis_client,
            db_client=db,
            mode="rich",
        )
        for i in range(IDEATOR_INSTANCES)
    ]
    coder = CoderAgent(redis_client, db)
    runner = BacktestRunner(redis_client)
    validator = ValidatorAgent(db)

    # Start ideators as background tasks
    ideator_tasks = [
        asyncio.create_task(ideator.run(), name=f"ideator_{i}")
        for i, ideator in enumerate(ideators)
    ]
    logger.info(f"Launched {len(ideator_tasks)} ideator background tasks")

    try:
        await pipeline_loop(
            db=db,
            redis_client=redis_client,
            ideators=ideators,
            coder=coder,
            runner=runner,
            validator=validator,
            end_time=end_time,
        )
    finally:
        logger.info("Shutting down ideators...")
        for ideator in ideators:
            await ideator.stop()
        for task in ideator_tasks:
            task.cancel()
        await asyncio.gather(*ideator_tasks, return_exceptions=True)

    # Final status report
    await status_report(db)

    # Print the SQL queries the user requested
    logger.info("Running verification queries...")
    async with db.engine.connect() as conn:
        r1 = await conn.execute(
            text("SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC")
        )
        print("\n=== SELECT status, COUNT(*) FROM strategies GROUP BY status ===")
        for row in r1.fetchall():
            print(f"  {row[0]:<28} {row[1]}")

        r2 = await conn.execute(
            text("SELECT COUNT(DISTINCT name) FROM strategies")
        )
        distinct = r2.scalar()
        print(f"\n=== SELECT COUNT(DISTINCT name) FROM strategies ===")
        print(f"  {distinct}")

    await redis_client.aclose()
    logger.info("Overnight generation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATLAS overnight generation loop")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=480,
        help="How long to run (default: 480 min / 8 hours)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.duration_minutes))
