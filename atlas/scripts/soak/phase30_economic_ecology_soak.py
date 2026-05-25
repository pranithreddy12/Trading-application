"""
phase30_economic_ecology_soak.py — Phase 30: Economic Densification & Adaptive Selection Pressure.

6-hour adaptive economic soak that exercises:
  - Trade density expansion (relaxed entry/exit filters)
  - Mutation ecology expansion (noisy mutations, reduced clone paranoia)
  - Regime stress engineering (synthetic perturbations)
  - Economic scarcity pressure (tight capital allocation, increased retirement)
  - Execution ecology activation (continuous fills, slippage variation)
  - Score-based organism competition (mutation leaderboard)
  - Scout trust divergence monitoring
  - Portfolio evolution tracking
  - Entropy governance
  - Lifecycle retirement

USAGE:
    python scripts/phase30_economic_ecology_soak.py --duration-minutes 360

METRICS PERSISTED TO:
    phase30_runtime_metrics table (created if not exists)
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.config.settings import settings


# ─────────────────────────────────────────────────────────
# METRICS COLLECTOR
# ─────────────────────────────────────────────────────────

class MetricsCollector:
    """Collects and persists Phase 30 runtime metrics every 5 minutes."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict] = []
        self._start_time: Optional[float] = None

    async def initialize(self):
        """Ensure the metrics table exists with extended Phase 30 columns."""
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase30_runtime_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT,
                    
                    -- Population metrics
                    strategies_generated INT,
                    validated_organisms INT,
                    active_organisms INT,
                    pending_backtest INT,
                    pending_validation INT,
                    pending_code INT,
                    
                    -- Trade density
                    trades_executed INT,
                    trade_throughput_24h INT,
                    avg_trades_per_strategy FLOAT,
                    
                    -- Mutation ecology
                    mutation_candidates INT,
                    mutation_family_count INT,
                    mutation_accept_rate FLOAT,
                    
                    -- Scout health
                    scout_trust_divergence FLOAT,
                    scout_agreement_score FLOAT,
                    scout_entropy FLOAT,
                    
                    -- Regime specialization
                    regime_diversity_count INT,
                    active_perturbations INT,
                    regime_stress_level FLOAT,
                    
                    -- Portfolio dynamics
                    portfolio_diversification FLOAT,
                    concentration_risk FLOAT,
                    capital_allocation_count INT,
                    retirement_count INT,
                    dominant_organisms INT,
                    
                    -- Execution realism
                    execution_degradation FLOAT,
                    avg_slippage_bps FLOAT,
                    avg_fill_probability FLOAT,
                    
                    -- System health
                    replay_integrity FLOAT,
                    lifecycle_events INT,
                    error_count INT,
                    
                    -- Phase 30 specific
                    economic_density_score FLOAT,
                    selection_pressure FLOAT,
                    regime_adaptation_score FLOAT,
                    
                    metadata JSONB
                )
            """))

            # Create index for time-based queries
            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase30_metrics_time 
                ON phase30_runtime_metrics (recorded_at)
            """))

        logger.info("Phase 30 metrics table initialized")

    async def collect(self, elapsed_minutes: int):
        """Collect a snapshot of all metrics."""
        metrics = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": elapsed_minutes,
        }

        # ─── Population metrics ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE((SELECT COUNT(*) FROM strategies), 0) AS total,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('validated', 'elite', 'live', 'promoted')), 0) AS validated,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('validated', 'elite', 'promoted', 'live', 'research_candidate', 'repair_candidate')), 0) AS active,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status = 'pending_backtest'), 0) AS pending_bt,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status = 'pending_validation'), 0) AS pending_val,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status = 'pending_code'), 0) AS pending_code,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('retired', 'failed_validation', 'code_failed', 'backtest_failed')), 0) AS retired,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE lifecycle_state = 'dominant'), 0) AS dominant
                    FROM (SELECT 1) dummy
                """))
                row = result.fetchone()
                if row:
                    metrics["strategies_generated"] = int(row[0])
                    metrics["validated_organisms"] = int(row[1])
                    metrics["active_organisms"] = int(row[2])
                    metrics["pending_backtest"] = int(row[3])
                    metrics["pending_validation"] = int(row[4])
                    metrics["pending_code"] = int(row[5])
                    metrics["retirement_count"] = int(row[6])
                    metrics["dominant_organisms"] = int(row[7])
        except Exception as e:
            logger.warning(f"Population metrics failed: {e}")

        # ─── Trade density ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(SUM(total_trades), 0) AS total_trades,
                        COALESCE((SELECT COUNT(*) FROM backtest_trades WHERE entry_time > NOW() - INTERVAL '24 hours'), 0) AS trade_throughput
                    FROM backtest_results
                """))
                row = result.fetchone()
                if row:
                    total_trades = int(row[0])
                    metrics["trades_executed"] = total_trades
                    metrics["trade_throughput_24h"] = int(row[1])
                    validated = metrics.get("validated_organisms", 1)
                    metrics["avg_trades_per_strategy"] = round(total_trades / max(1, validated), 2)
        except Exception as e:
            logger.warning(f"Trade metrics failed: {e}")

        # ─── Mutation ecology ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(COUNT(*), 0) AS mutation_count,
                        COALESCE(COUNT(DISTINCT mutation_type), 0) AS family_count
                    FROM mutation_memory
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """))
                row = result.fetchone()
                if row:
                    metrics["mutation_candidates"] = int(row[0])
                    metrics["mutation_family_count"] = int(row[1])
        except Exception as e:
            logger.warning(f"Mutation metrics failed: {e}")

        # ─── Scout health ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(MAX(dynamic_trust_score) - MIN(dynamic_trust_score), 0) AS trust_divergence,
                        COALESCE(AVG(dynamic_trust_score), 0.5) AS avg_trust
                    FROM source_performance_log
                    WHERE updated_at > NOW() - INTERVAL '24 hours'
                """))
                row = result.fetchone()
                if row:
                    metrics["scout_trust_divergence"] = round(float(row[0]), 4)
        except Exception as e:
            logger.warning(f"Scout metrics failed: {e}")

        # ─── Portfolio dynamics ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT diversification_score, concentration_risk
                    FROM portfolio_intelligence
                    ORDER BY computed_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    metrics["portfolio_diversification"] = round(float(row[0]), 4) if row[0] else 0
                    metrics["concentration_risk"] = round(float(row[1]), 4) if row[1] else 0
        except Exception as e:
            logger.warning(f"Portfolio metrics failed: {e}")

        # ─── Regime stress ───
        metrics.setdefault("regime_diversity_count", 0)
        metrics.setdefault("active_perturbations", 0)
        metrics.setdefault("regime_stress_level", 0.0)
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(COUNT(DISTINCT perturbation_type), 0) AS perturbation_types,
                        COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0) AS active_perturbations
                    FROM regime_perturbation_events
                    WHERE started_at > NOW() - INTERVAL '1 hour'
                """))
                row = result.fetchone()
                if row:
                    metrics["regime_diversity_count"] = int(row[0])
                    metrics["active_perturbations"] = int(row[1])
                    metrics["regime_stress_level"] = round(min(1.0, int(row[1]) / 3.0), 4)
        except Exception as e:
            logger.warning(f"Regime stress metrics failed: {e}")

        # ─── Execution realism ───
        metrics.setdefault("execution_degradation", 0.0)
        metrics.setdefault("avg_slippage_bps", 0.0)
        metrics.setdefault("avg_fill_probability", 0.0)
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT execution_degradation_score, avg_expected_slippage_bps, avg_fill_probability
                    FROM execution_realism
                    ORDER BY simulated_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    metrics["execution_degradation"] = round(float(row[0]), 4) if row[0] else 0
                    metrics["avg_slippage_bps"] = round(float(row[1]), 2) if row[1] else 0
                    metrics["avg_fill_probability"] = round(float(row[2]), 4) if row[2] else 0
        except Exception as e:
            logger.warning(f"Execution realism metrics failed: {e}")

        # ─── Scout entropy ───
        metrics.setdefault("scout_entropy", 0.5)
        metrics.setdefault("scout_agreement_score", 0.5)
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT disagreement_entropy, scout_agreement_score
                    FROM scout_synthesis_log
                    ORDER BY created_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    metrics["scout_entropy"] = round(float(row[0]), 4) if row[0] else 0.5
                    metrics["scout_agreement_score"] = round(float(row[1]), 4) if row[1] else 0.5
        except Exception as e:
            logger.warning(f"Scout entropy metrics failed: {e}")

        # ─── Composite Phase 30 scores ───
        metrics = self._compute_phase30_scores(metrics)

        # Persist to DB
        await self._persist(metrics)
        self.metrics_history.append(metrics)

        return metrics

    def _compute_phase30_scores(self, metrics: dict) -> dict:
        """Compute Phase 30-specific composite scores."""
        validated = metrics.get("validated_organisms", 0)
        active = metrics.get("active_organisms", 0)
        trades = metrics.get("trades_executed", 0)
        mutations = metrics.get("mutation_candidates", 0)

        # Economic Density Score: how much economic activity is happening
        # Factors: validated organisms, trades, mutations, active population
        density = (
            min(1.0, validated / 20) * 0.25
            + min(1.0, trades / 200) * 0.35
            + min(1.0, mutations / 50) * 0.25
            + min(1.0, active / 15) * 0.15
        )
        metrics["economic_density_score"] = round(density * 100, 1)

        # Selection Pressure: how much competition is forcing evolution
        retired = metrics.get("retirement_count", 0)
        div_score = metrics.get("portfolio_diversification", 0)
        pressure = (
            min(1.0, retired / 10) * 0.30  # Retirement activity
            + (1.0 - (div_score or 0.5)) * 0.25  # Concentration risk
            + min(1.0, mutations / 30) * 0.25  # Mutation competition
            + min(1.0, validated / max(1, active)) * 0.20  # Validation ratio
        )
        metrics["selection_pressure"] = round(pressure * 100, 1)

        # Regime Adaptation Score: how well organisms handle diversity
        stress_level = metrics.get("regime_stress_level", 0)
        regime_div = metrics.get("regime_diversity_count", 0)
        adaptation = (
            min(1.0, regime_div / 5) * 0.30
            + max(0, 1.0 - stress_level) * 0.30
            + min(1.0, validated / 10) * 0.40
        )
        metrics["regime_adaptation_score"] = round(adaptation * 100, 1)

        return metrics

    def _ensure_defaults(self, metrics: dict) -> dict:
        """Ensure all expected metric keys have default values to prevent INSERT failures."""
        defaults = {
            "strategies_generated": 0, "validated_organisms": 0, "active_organisms": 0,
            "pending_backtest": 0, "pending_validation": 0, "pending_code": 0,
            "trades_executed": 0, "trade_throughput_24h": 0, "avg_trades_per_strategy": 0.0,
            "mutation_candidates": 0, "mutation_family_count": 0, "mutation_accept_rate": 0.0,
            "scout_trust_divergence": 0.0, "scout_agreement_score": 0.5, "scout_entropy": 0.5,
            "regime_diversity_count": 0, "active_perturbations": 0, "regime_stress_level": 0.0,
            "portfolio_diversification": 0.5, "concentration_risk": 0.0,
            "capital_allocation_count": 0, "retirement_count": 0, "dominant_organisms": 0,
            "execution_degradation": 0.0, "avg_slippage_bps": 0.0, "avg_fill_probability": 0.0,
            "replay_integrity": 1.0, "lifecycle_events": 0, "error_count": 0,
            "economic_density_score": 0.0, "selection_pressure": 0.0, "regime_adaptation_score": 0.0,
        }
        for k, v in defaults.items():
            if k not in metrics:
                metrics[k] = v
        return metrics

    async def _persist(self, metrics: dict) -> bool:
        """Persist metrics snapshot to phase30_runtime_metrics. Returns True on success."""
        metrics = self._ensure_defaults(metrics)
        try:
            async with self.engine.begin() as conn:
                await conn.execute(sa_text("""
                    INSERT INTO phase30_runtime_metrics (
                        recorded_at, runtime_minutes,
                        strategies_generated, validated_organisms, active_organisms,
                        pending_backtest, pending_validation, pending_code,
                        trades_executed, trade_throughput_24h, avg_trades_per_strategy,
                        mutation_candidates, mutation_family_count,
                        scout_trust_divergence, scout_agreement_score, scout_entropy,
                        regime_diversity_count, active_perturbations, regime_stress_level,
                        portfolio_diversification, concentration_risk,
                        retirement_count, dominant_organisms,
                        execution_degradation, avg_slippage_bps, avg_fill_probability,
                        economic_density_score, selection_pressure, regime_adaptation_score,
                        metadata
                    ) VALUES (
                        :recorded_at, :runtime_minutes,
                        :strategies_generated, :validated_organisms, :active_organisms,
                        :pending_backtest, :pending_validation, :pending_code,
                        :trades_executed, :trade_throughput_24h, :avg_trades_per_strategy,
                        :mutation_candidates, :mutation_family_count,
                        :scout_trust_divergence, :scout_agreement_score, :scout_entropy,
                        :regime_diversity_count, :active_perturbations, :regime_stress_level,
                        :portfolio_diversification, :concentration_risk,
                        :retirement_count, :dominant_organisms,
                        :execution_degradation, :avg_slippage_bps, :avg_fill_probability,
                        :economic_density_score, :selection_pressure, :regime_adaptation_score,                    :metadata
                )
                """), metrics | {"metadata": json.dumps({
                    "recorded_at": metrics["recorded_at"].isoformat() if hasattr(metrics["recorded_at"], 'isoformat') else str(metrics["recorded_at"]),
                    "runtime_minutes": metrics["runtime_minutes"],
                })})
            return True
        except Exception as e:
            logger.warning(f"Persist metrics failed: {e}")
            return False

    async def get_summary(self) -> dict:
        """Compute final summary from accumulated metrics."""
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        initial = self.metrics_history[0] if len(self.metrics_history) > 1 else latest

        # Compute deltas
        deltas = {}
        for key in ["strategies_generated", "validated_organisms", "active_organisms",
                     "trades_executed", "mutation_candidates", "retirement_count",
                     "economic_density_score", "selection_pressure", "regime_adaptation_score"]:
            old_val = initial.get(key, 0) if isinstance(initial.get(key), (int, float)) else 0
            new_val = latest.get(key, 0) if isinstance(latest.get(key), (int, float)) else 0
            deltas[key] = {
                "start": old_val,
                "end": new_val,
                "delta": new_val - old_val,
            }

        return {
            "duration_minutes": latest.get("runtime_minutes", 0),
            "n_snapshots": len(self.metrics_history),
            "latest_snapshot": latest,
            "deltas": deltas,
            "final_scores": {
                "economic_density": latest.get("economic_density_score", 0),
                "selection_pressure": latest.get("selection_pressure", 0),
                "regime_adaptation": latest.get("regime_adaptation_score", 0),
            },
        }

    async def close(self):
        await self.engine.dispose()


# ─────────────────────────────────────────────────────────
# SOAK CONTROLLER
# ─────────────────────────────────────────────────────────

class SoakController:
    """Controls the Phase 30 economic ecology soak run."""

    def __init__(self, duration_minutes: int = 360):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = 300  # Every 5 minutes
        self.db_url = settings.database_url
        self.metrics = MetricsCollector(self.db_url)
        self._shutdown = False
        self._start_time: Optional[float] = None

    async def run(self):
        """Run the full soak cycle."""
        logger.info("=" * 70)
        logger.info("PHASE 30 — ECONOMIC ECOLOGY SOAK STARTING")
        logger.info(f"Duration: {self.duration_minutes} minutes ({self.duration_seconds}s)")
        logger.info(f"Metrics interval: {self.metrics_interval}s (every 5 min)")
        logger.info("=" * 70)

        # Initialize metrics table
        await self.metrics.initialize()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        self._start_time = time.time()

        try:
            # Main soak loop
            while not self._shutdown:
                elapsed = time.time() - self._start_time
                remaining = self.duration_seconds - elapsed

                if remaining <= 0:
                    logger.info("Soak duration reached — completing")
                    break

                elapsed_minutes = int(elapsed / 60)

                # Collect metrics
                metrics = await self.metrics.collect(elapsed_minutes)

                # Print progress
                self._print_status(metrics, elapsed, remaining)

                # Wait for next collection interval
                await asyncio.sleep(min(self.metrics_interval, remaining))

        except asyncio.CancelledError:
            logger.info("Soak cancelled")
        except Exception as e:
            logger.error(f"Soak error: {e}", exc_info=True)
        finally:
            await self._finalize()

    def _handle_shutdown(self):
        """Handle graceful shutdown signal."""
        logger.info("Shutdown signal received — completing soak")
        self._shutdown = True

    def _print_status(self, metrics: dict, elapsed: float, remaining: float):
        """Print current soak status."""
        elapsed_min = int(elapsed / 60)
        remaining_min = int(remaining / 60)

        density = metrics.get("economic_density_score", 0)
        pressure = metrics.get("selection_pressure", 0)
        adaptation = metrics.get("regime_adaptation_score", 0)

        gen = metrics.get("strategies_generated", 0)
        val = metrics.get("validated_organisms", 0)
        act = metrics.get("active_organisms", 0)
        trades = metrics.get("trades_executed", 0)
        muts = metrics.get("mutation_candidates", 0)
        retired = metrics.get("retirement_count", 0)
        perturbations = metrics.get("active_perturbations", 0)

        print(f"\n[Phase30] T+{elapsed_min}m / T-{remaining_min}m  "
              f"Density={density:.1f}  Pressure={pressure:.1f}  Adaptation={adaptation:.1f}")
        print(f"  Population: {gen} gen | {val} val | {act} act | {retired} retired")
        print(f"  Ecology: {trades} trades | {muts} mutations | {perturbations} perturbations")
        print(f"  Pipeline: BT={metrics.get('pending_backtest',0)} "
              f"VL={metrics.get('pending_validation',0)} "
              f"CD={metrics.get('pending_code',0)}")
        print(f"  Diversification={metrics.get('portfolio_diversification',0):.2f} "
              f"Concentration={metrics.get('concentration_risk',0):.2f}")
        sys.stdout.flush()

    async def _finalize(self):
        """Finalize soak and generate summary."""
        final_elapsed = time.time() - self._start_time if self._start_time else 0
        final_minutes = int(final_elapsed / 60)

        print(f"\n{'=' * 70}")
        print(f"PHASE 30 SOAK COMPLETE — {final_minutes} minutes elapsed")
        print(f"{'=' * 70}")

        summary = await self.metrics.get_summary()
        print(json.dumps(summary, indent=2, default=str))

        await self.metrics.close()


# ─────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Phase 30: Economic Ecology Soak — 6-hour adaptive evolution test"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=360,
        help="Soak duration in minutes (default: 360 = 6 hours)",
    )
    parser.add_argument(
        "--metrics-interval",
        type=int,
        default=300,
        help="Metrics collection interval in seconds (default: 300 = 5 min)",
    )
    args = parser.parse_args()

    controller = SoakController(
        duration_minutes=args.duration_minutes,
    )
    controller.metrics_interval = args.metrics_interval

    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
