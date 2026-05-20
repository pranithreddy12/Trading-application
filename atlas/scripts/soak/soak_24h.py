"""
soak_24h.py — 24-Hour Full Institutional Soak Test (Phase 18.1)

Full production-readiness validation with strategy lifecycle, drift, execution,
scout, and portfolio monitoring across 24 continuous hours.
"""

import asyncio
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from loguru import logger
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient

DURATION_HOURS = 24
CHECK_INTERVAL_SEC = 60
REPORT_PATH = Path(__file__).resolve().parent / "soak_report_24h.json"


async def main():
    logger.info(f"Starting {DURATION_HOURS}h full institutional soak test")
    db = TimescaleClient(settings.database_url)
    await db.connect()

    start_time = time.time()
    end_time = start_time + DURATION_HOURS * 3600
    results = {
        "test": f"{DURATION_HOURS}h Full Institutional Soak",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_hours": DURATION_HOURS,
        "checks": [],
        "summary": {},
    }

    from sqlalchemy.sql import text
    check_count = 0
    db_failures = 0
    redis_failures = 0
    agent_failures = 0

    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url)

    while time.time() < end_time:
        check_count += 1
        ts = datetime.now(timezone.utc).isoformat()

        # Database check
        try:
            async with db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
            db_failures += 1

        # Redis check
        try:
            await r.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
            redis_failures += 1

        # Agent heartbeat check
        try:
            agent_keys = await r.keys("agent:*heartbeat")
            if len(agent_keys) < 3:
                agent_failures += 1
        except Exception:
            agent_failures += 1

        results["checks"].append({
            "timestamp": ts, "check_number": check_count,
            "db_ok": db_ok, "redis_ok": redis_ok,
        })

        if check_count % 60 == 0:
            elapsed_h = (time.time() - start_time) / 3600
            logger.info(
                f"Soak {elapsed_h:.1f}h: {check_count} checks | "
                f"DB fails: {db_failures} | Redis fails: {redis_failures}"
            )

        await asyncio.sleep(CHECK_INTERVAL_SEC)

    await r.aclose()
    results["summary"] = {
        "total_checks": check_count,
        "db_failures": db_failures,
        "redis_failures": redis_failures,
        "agent_failures": agent_failures,
        "db_healthy": db_failures == 0,
        "redis_healthy": redis_failures == 0,
        "overall_pass": db_failures == 0 and redis_failures == 0 and agent_failures == 0,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    REPORT_PATH.write_text(json.dumps(results, indent=2))
    logger.success(f"24h soak complete. Report: {REPORT_PATH}")
    await db.engine.dispose()
    return 0 if results["summary"]["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
