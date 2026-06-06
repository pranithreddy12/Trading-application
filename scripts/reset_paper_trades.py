"""
reset_paper_trades.py — Reset all paper trade, position, and execution data.

Clears: paper_trades, positions, execution_log, execution_dead_letter,
        copy_execution_log, copy_drift_log, copy_position_state,
        execution_realism, and resets risk_state.

Keeps: strategies, backtest_results, features, market_data — everything needed
       for the soak test to generate fresh trades.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger
from sqlalchemy.sql import text
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


TABLES_TO_CLEAR = [
    "paper_trades",
    "positions",
    "execution_log",
    "execution_dead_letter",
    "copy_execution_log",
    "copy_drift_log",
    "copy_position_state",
    "copy_replay_events",
    "copy_quality_metrics",
    "copy_overlap_metrics",
    "copy_failover_events",
    "follower_reconciliation",
    "leader_health_metrics",
    "execution_realism",
    "capital_preservation_state",
    "stress_test_results",
    "systemic_risk",
    "deployment_governance",
    "replay_integrity",
    "system_health",
    "portfolio_intelligence",
    "capital_allocation",
    "ensemble_execution",
    "drift_detection",
    "strategy_retirement",
    "failed_inserts",
    "scout_quarantine",
    "scout_signals",
    "external_scout_memory",
    "scout_mirror_debug_log",
    "scout_influence_log",
    "scout_economic_attribution",
    "scout_signal_attribution",
    "source_performance_log",
    "scout_poison_quarantine",
    "meta_reasoning_log",
    "hypothesis_registry",
    "failure_analysis",
    "mutation_policy_log",
    "scout_synthesis_log",
    "monitoring_metrics",
    "anomaly_observations",
]


async def reset_database():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect(run_migrations=False)

    cleared = 0
    failed = 0

    for table in TABLES_TO_CLEAR:
        try:
            async with db.engine.begin() as conn:
                await conn.execute(text(f"DELETE FROM {table}"))
                cleared += 1
            logger.info(f"✅ Cleared {table}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to clear {table}: {e}")
            failed += 1

    # Reset risk_state to halted=FALSE
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE risk_state
                    SET halted = FALSE, reason = 'reset_for_soak_test', released_at = NOW(), updated_at = NOW()
                    WHERE scope = 'portfolio'
                """)
            )
        logger.info("✅ Reset risk_state (kill switch = FALSE)")
        cleared += 1
    except Exception as e:
        logger.warning(f"⚠️  Failed to reset risk_state: {e}")
        failed += 1

    # Reset copy_leader_accounts and copy_follower_accounts if they exist
    for table in ["copy_leader_accounts", "copy_follower_accounts"]:
        try:
            async with db.engine.begin() as conn:
                await conn.execute(text(f"UPDATE {table} SET is_active = FALSE"))
            logger.info(f"✅ Deactivated {table}")
        except Exception:
            pass  # Table may not exist

    logger.info(f"\n{'='*50}")
    logger.info(f"Reset complete: {cleared} tables cleared, {failed} failed")
    logger.info(f"{'='*50}")

    # Verify key tables are empty
    async with db.engine.connect() as conn:
        for table in ["paper_trades", "positions", "execution_log", "execution_dead_letter"]:
            try:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = r.scalar() or 0
                logger.info(f"  {table}: {count} rows remaining")
            except Exception as e:
                logger.info(f"  {table}: ERROR - {e}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(reset_database())
