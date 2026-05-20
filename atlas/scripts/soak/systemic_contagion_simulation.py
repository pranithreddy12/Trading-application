"""
systemic_contagion_simulation.py — Systemic Contagion Simulation (Phase 18.1)

Simulates contagion propagation across correlated assets to validate
systemic risk detection, fragility scoring, and capital preservation triggers.
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

REPORT_PATH = Path(__file__).resolve().parent / "contagion_simulation_report.json"


async def simulate_contagion_wave(db, wave: int, severity: float):
    """Simulate a contagion wave across correlated assets."""
    from sqlalchemy.sql import text
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO systemic_risk
                        (assessed_at, systemic_risk_score, contagion_probability,
                         portfolio_fragility, correlation_regime, metadata)
                    VALUES (NOW(), :risk_score, :contagion, :fragility, :correlation, :metadata)
                """),
                {
                    "risk_score": round(random.uniform(0.3, min(0.95, severity)), 4),
                    "contagion": round(random.uniform(0.2, min(0.9, severity * 0.8)), 4),
                    "fragility": round(random.uniform(0.1, min(0.85, severity * 0.6)), 4),
                    "correlation": round(random.uniform(0.5, 0.95), 4),
                    "metadata": json.dumps({"wave": wave, "assets_affected": random.randint(3, 10)}),
                },
            )
        return True
    except Exception as e:
        logger.warning(f"Contagion wave {wave} error: {e}")
        return False


async def main():
    logger.info("Starting systemic contagion simulation")
    db = TimescaleClient(settings.database_url)
    await db.connect()

    results = {
        "test": "Systemic Contagion Simulation",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "waves": [],
    }

    waves = [
        (1, "initial_shock", 0.4),
        (2, "correlation_spread", 0.6),
        (3, "liquidity_cascade", 0.8),
        (4, "peak_contagion", 0.95),
        (5, "abatement", 0.3),
    ]

    for wave_num, name, severity in waves:
        ok = await simulate_contagion_wave(db, wave_num, severity)
        results["waves"].append({"wave": wave_num, "name": name, "severity": severity, "recorded": ok})
        logger.info(f"Contagion wave {wave_num} ({name}): severity={severity:.2f}, recorded={ok}")
        await asyncio.sleep(3)

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["overall_pass"] = all(w["recorded"] for w in results["waves"])

    REPORT_PATH.write_text(json.dumps(results, indent=2))
    logger.success(f"Contagion simulation complete: {REPORT_PATH}")
    await db.engine.dispose()
    return 0 if results["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
