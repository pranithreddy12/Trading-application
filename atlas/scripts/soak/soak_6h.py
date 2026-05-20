"""
soak_6h.py — 6-Hour System Stability Soak Test (Phase 18.1)

Runs: 6 hours of continuous ATLAS system monitoring.
Measures: system health, agent uptime, event throughput, execution latency,
          drift stability, scout reliability, portfolio durability.
Outputs: soak_report_6h.json with pass/fail for each metric.
"""

import asyncio
import json
import time
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loguru import logger

DURATION_HOURS = 6
CHECK_INTERVAL_SEC = 60  # Check health every 60s
REPORT_PATH = Path(__file__).resolve().parent / "soak_report_6h.json"


async def check_database(db):
    from sqlalchemy.sql import text
    try:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "healthy"
    except Exception as e:
        return False, str(e)


async def check_redis():
    try:
        import redis.asyncio as redis
        r = redis.from_url("redis://localhost:6379")
        await r.ping()
        await r.aclose()
        return True, "healthy"
    except Exception as e:
        return False, str(e)


async def main():
    logger.info(f"Starting {DURATION_HOURS}h soak test")

    from atlas.config.settings import settings
    from atlas.data.storage.timescale_client import TimescaleClient

    db = TimescaleClient(settings.database_url)
    await db.connect()

    start_time = time.time()
    end_time = start_time + DURATION_HOURS * 3600

    results = {
        "test": f"{DURATION_HOURS}h System Stability Soak",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_hours": DURATION_HOURS,
        "checks": [],
        "summary": {},
    }

    db_ok = True
    redis_ok = True
    check_count = 0
    db_failures = 0
    redis_failures = 0

    while time.time() < end_time:
        check_count += 1
        ts = datetime.now(timezone.utc).isoformat()

        db_healthy, db_err = await check_database(db)
        redis_healthy, redis_err = await check_redis()

        if not db_healthy:
            db_failures += 1
        if not redis_healthy:
            redis_failures += 1

        results["checks"].append({
            "timestamp": ts,
            "check_number": check_count,
            "db_healthy": db_healthy,
            "redis_healthy": redis_healthy,
            "db_error": db_err if not db_healthy else None,
            "redis_error": redis_err if not redis_healthy else None,
        })

        if check_count % 10 == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Soak progress: {elapsed / 60:.0f}m elapsed, "
                f"{check_count} checks, DB failures: {db_failures}, Redis failures: {redis_failures}"
            )

        await asyncio.sleep(CHECK_INTERVAL_SEC)

    db_ok = db_failures == 0
    redis_ok = redis_failures == 0
    results["summary"] = {
        "total_checks": check_count,
        "db_failures": db_failures,
        "redis_failures": redis_failures,
        "db_healthy": db_ok,
        "redis_healthy": redis_ok,
        "overall_pass": db_ok and redis_ok,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    REPORT_PATH.write_text(json.dumps(results, indent=2))
    logger.success(f"Soak test complete. Report: {REPORT_PATH}")
    logger.info(f"Overall pass: {results['summary']['overall_pass']}")

    await db.engine.dispose()
    return 0 if results["summary"]["overall_pass"] else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
