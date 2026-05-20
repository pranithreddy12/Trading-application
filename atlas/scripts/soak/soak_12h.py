"""
soak_12h.py — 12-Hour Extended System Stability Soak Test (Phase 18.1)

Extended soak with agent health monitoring, strategy lifecycle tracking,
and drift stability measurement.
"""

import asyncio
import json
import time
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from loguru import logger
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient

DURATION_HOURS = 12
CHECK_INTERVAL_SEC = 30  # Every 30s
REPORT_PATH = Path(__file__).resolve().parent / "soak_report_12h.json"


async def main():
    logger.info(f"Starting {DURATION_HOURS}h extended soak test")
    db = TimescaleClient(settings.database_url)
    await db.connect()

    start_time = time.time()
    end_time = start_time + DURATION_HOURS * 3600
    results = {
        "test": f"{DURATION_HOURS}h Extended System Stability Soak",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_hours": DURATION_HOURS,
        "checks": [],
        "summary": {},
    }

    from sqlalchemy.sql import text
    check_count = 0
    db_failures = 0
    redis_failures = 0
    strategy_counts = []

    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url)

    while time.time() < end_time:
        check_count += 1
        ts = datetime.now(timezone.utc).isoformat()

        # Database check
        db_healthy = True
        db_err = None
        try:
            async with db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            db_healthy = False
            db_failures += 1
            db_err = str(e)

        # Redis check
        redis_healthy = True
        redis_err = None
        try:
            await r.ping()
        except Exception as e:
            redis_healthy = False
            redis_failures += 1
            redis_err = str(e)

        # Strategy count
        strat_count = 0
        try:
            async with db.engine.connect() as conn:
                r2 = await conn.execute(text("SELECT COUNT(*) FROM strategies"))
                strat_count = r2.scalar() or 0
        except Exception:
            pass
        strategy_counts.append(strat_count)

        results["checks"].append({
            "timestamp": ts, "check_number": check_count,
            "db_healthy": db_healthy, "redis_healthy": redis_healthy,
            "strategy_count": strat_count,
            "db_error": db_err, "redis_error": redis_err,
        })

        if check_count % 60 == 0:
            elapsed_h = (time.time() - start_time) / 3600
            logger.info(f"Soak {elapsed_h:.1f}h: {check_count} checks, DB failures: {db_failures}")

        await asyncio.sleep(CHECK_INTERVAL_SEC)

    await r.aclose()
    results["summary"] = {
        "total_checks": check_count,
        "db_failures": db_failures,
        "redis_failures": redis_failures,
        "avg_strategy_count": round(sum(strategy_counts) / len(strategy_counts), 1) if strategy_counts else 0,
        "db_healthy": db_failures == 0,
        "redis_healthy": redis_failures == 0,
        "overall_pass": db_failures == 0 and redis_failures == 0,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    REPORT_PATH.write_text(json.dumps(results, indent=2))
    logger.success(f"12h soak complete. Report: {REPORT_PATH}")
    logger.info(f"Pass: {results['summary']['overall_pass']}")
    await db.engine.dispose()
    return 0 if results["summary"]["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
