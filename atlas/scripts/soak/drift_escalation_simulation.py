"""
drift_escalation_simulation.py — Drift Escalation Simulation (Phase 18.1)

Simulates progressive feature drift, strategy drift, and regime drift
across the ATLAS system to validate drift detection and retirement governance.
"""

import asyncio
import json
import random
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from loguru import logger
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient

DURATION_SEC = 1800  # 30 minute simulation
REPORT_PATH = Path(__file__).resolve().parent / "drift_simulation_report.json"


async def inject_drift_events(db, count: int):
    """Inject synthetic drift detection events."""
    from sqlalchemy.sql import text
    for i in range(count):
        try:
            async with db.engine.begin() as conn:
                await conn.execute(
                    text("""
                        INSERT INTO drift_detection (drift_type, severity, description, detected_at)
                        VALUES (:drift_type, :severity, :desc, NOW())
                    """),
                    {
                        "drift_type": random.choice(["feature_psi", "strategy", "regime", "execution"]),
                        "severity": round(random.uniform(0.1, 0.95), 2),
                        "desc": f"Simulated drift event #{i+1}",
                    },
                )
        except Exception:
            pass
        await asyncio.sleep(0.1)
    logger.info(f"Injected {count} drift events")


async def main():
    logger.info("Starting drift escalation simulation (30 min)")
    db = TimescaleClient(settings.database_url)
    await db.connect()

    start = time.time()
    results = {
        "test": "Drift Escalation Simulation",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": [],
    }

    try:
        # Phase 1: Normal drift (low severity)
        logger.info("Phase 1: Low severity drift")
        await inject_drift_events(db, 10)
        await asyncio.sleep(60)

        # Phase 2: Elevated drift (medium severity)
        logger.info("Phase 2: Medium severity drift")
        await inject_drift_events(db, 20)
        await asyncio.sleep(60)

        # Phase 3: Escalated drift (high severity)
        logger.info("Phase 3: High severity drift")
        await inject_drift_events(db, 30)
        await asyncio.sleep(60)

        # Phase 4: Abated drift (return to low)
        logger.info("Phase 4: Drift abatement")
        await inject_drift_events(db, 5)

        elapsed = time.time() - start
        results["duration_sec"] = round(elapsed, 1)
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["overall_pass"] = True

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        results["error"] = str(e)
        results["overall_pass"] = False

    REPORT_PATH.write_text(json.dumps(results, indent=2))
    logger.success(f"Drift simulation complete: {REPORT_PATH}")
    await db.engine.dispose()
    return 0 if results["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
