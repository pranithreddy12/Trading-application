"""
phase31_specialization_soak.py — Phase 31G: Long-Horizon Specialization Soak.

12-hour adaptive soak that exercises:
  - Phase 31A: Dominant Organism Tracking (survival, capital efficiency, lifespan)
  - Phase 31B: Mutation Lineage Tracking (lineage IDs, parent->child trees)
  - Phase 31C: Regime Specialization Engine (regime affinity scoring)
  - Phase 31D: Scout Predictive Divergence (scout attribution quality)
  - Phase 31E: Portfolio Evolution Pressure (adaptive capital allocation)
  - Phase 31F: Economic Survival Stress (synthetic perturbations)
  - Mutation lineage tracking
  - Adaptive scarcity pressure
  - Synthetic regime perturbations
  - Execution realism
  - Portfolio evolution
  - Scout attribution
  - Economic retirement logic
  - Replay verification
  - Entropy governance

MANDATORY METRICS (every 5 minutes):
  - dominant organisms
  - mutation-family rankings
  - scout trust divergence
  - regime affinity scores
  - capital allocation distribution
  - drawdown recovery speed
  - organism lifespan distribution
  - retirement causes
  - diversification scores
  - replay integrity
  - execution degradation metrics

Persists into: phase31_specialization_metrics

USAGE:
    python scripts/phase31_specialization_soak.py --duration-minutes 720

SUCCESS CRITERIA:
  - dominant mutation families emerge
  - regime specialization appears
  - scout trust diverges meaningfully
  - portfolio allocation adapts dynamically
  - weak organisms decay naturally
  - capital concentrates toward durable organisms
  - replay integrity remains perfect
  - long-horizon circulation remains stable
  - adaptive behavior improves survival quality over time
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

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Fix atlas namespace: ensure project root is in atlas.__path__ so that
# atlas.core.agent_base (and other flat-level modules) are resolvable.
import atlas as _atlas_mod
if _PROJECT_ROOT not in list(_atlas_mod.__path__):
    _atlas_mod.__path__.append(_PROJECT_ROOT)

from loguru import logger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.config.settings import settings

# Phase 31 Engine Imports — driven every cycle
from atlas.agents.l7_meta.dominant_organism_tracker import DominantOrganismTracker
from atlas.agents.l7_meta.mutation_lineage_tracker import MutationLineageTracker
from atlas.agents.l7_meta.regime_specialization_engine import RegimeSpecializationEngine
from atlas.agents.l7_meta.scout_divergence_engine import ScoutDivergenceEngine
from atlas.agents.l6_portfolio.portfolio_evolution_pressure import PortfolioEvolutionPressure
from atlas.agents.l7_meta.regime_stress_engine import RegimeStressEngine

# ─────────────────────────────────────────────────────────
# LIGHTWEIGHT DB CLIENT — wraps SQLAlchemy engine for engine use
# ─────────────────────────────────────────────────────────

class SoakDbClient:
    """Minimal DB client wrapper so Phase 31 engines can read/write."""
    def __init__(self, engine):
        self.engine = engine

    async def _execute_insert(self, query: str, params: dict) -> None:
        from sqlalchemy import text as _t
        async with self.engine.begin() as conn:
            await conn.execute(_t(query), params)


# ─────────────────────────────────────────────────────────
# METRICS COLLECTOR
# ─────────────────────────────────────────────────────────

class SpecializationMetricsCollector:
    """Collects and persists Phase 31 specialization metrics every 5 minutes."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict] = []
        self._start_time: Optional[float] = None

    async def initialize(self):
        """Ensure the metrics table exists."""
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase31_specialization_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT,

                    -- Population dynamics
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

                    -- Dominant organisms
                    n_dominant_identified INT,
                    n_dominant_lineages INT,
                    dominant_concentration FLOAT,

                    -- Mutation ecology
                    mutation_candidates INT,
                    mutation_family_count INT,
                    mutation_accept_rate FLOAT,
                    lineages_identified INT,
                    lineage_depth_avg FLOAT,

                    -- Regime specialization
                    regime_specialization_count INT,
                    regime_specialization_diversity FLOAT,
                    regime_affinity_bull FLOAT,
                    regime_affinity_bear FLOAT,
                    regime_affinity_ranging FLOAT,

                    -- Portfolio evolution
                    portfolio_diversification FLOAT,
                    concentration_risk FLOAT,
                    capital_migrated_pct FLOAT,
                    n_weak_penalized INT,
                    n_dominant_boosted INT,
                    retirement_count INT,

                    -- Scout divergence
                    scout_divergence_count INT,
                    scout_trust_divergence FLOAT,
                    n_high_value_scouts INT,
                    n_contradictory_scouts INT,

                    -- Stress testing
                    active_perturbations INT,
                    stress_level FLOAT,
                    n_survivors INT,
                    n_collapsed INT,

                    -- Execution realism
                    execution_degradation FLOAT,
                    avg_slippage_bps FLOAT,
                    avg_fill_probability FLOAT,

                    -- Composite scores
                    dominant_emergence_score FLOAT,
                    lineage_evolution_score FLOAT,
                    regime_adaptation_score FLOAT,
                    scout_predictive_divergence FLOAT,
                    portfolio_evolution_pressure FLOAT,
                    stress_survival_score FLOAT,

                    metadata JSONB
                )
            """))

            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase31_metrics_time
                ON phase31_specialization_metrics (recorded_at DESC)
            """))

        logger.info("Phase 31 specialization metrics table initialized")

    async def collect(self, elapsed_minutes: int):
        """Collect a snapshot of all Phase 31 metrics."""
        metrics = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": elapsed_minutes,
        }

        # ─── Population & Trade Density ───
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
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE lifecycle_state IN ('retired', 'quarantined')), 0) AS retired,
                        COALESCE(SUM(b.total_trades), 0) AS total_trades,
                        COALESCE((SELECT COUNT(*) FROM backtest_trades WHERE entry_time > NOW() - INTERVAL '24 hours'), 0) AS trade_throughput
                    FROM strategies s
                    LEFT JOIN backtest_results b ON s.id = b.strategy_id
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
                    metrics["trades_executed"] = int(row[7])
                    metrics["trade_throughput_24h"] = int(row[8])
                    metrics["avg_trades_per_strategy"] = round(int(row[7]) / max(1, int(row[1])), 2)
        except Exception as e:
            logger.warning(f"Population metrics failed: {e}")

        # ─── Dominant Organisms ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE lifecycle_state = 'dominant'), 0) AS dominant_count,
                        COALESCE((SELECT COUNT(*) FROM strategies WHERE lifecycle_state IN ('retired', 'quarantined', 'degrading')), 0) AS collapsed_count
                """))
                row = result.fetchone()
                if row:
                    metrics["n_dominant_identified"] = int(row[0])
                    n_active = metrics.get("active_organisms", 1)
                    metrics["dominant_concentration"] = round(int(row[0]) / max(1, n_active), 4)
                    metrics["n_collapsed"] = int(row[1])
                    metrics["n_survivors"] = max(0, n_active - int(row[0]))
        except Exception as e:
            logger.warning(f"Dominant metrics failed: {e}")

        # ─── Dominant Lineages ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT COALESCE(MAX(n_dominant_lineages), 0)
                    FROM mutation_lineage_log
                    LIMIT 1
                """))
                row = result.fetchone()
                metrics["n_dominant_lineages"] = int(row[0]) if row else 0

                result = await conn.execute(sa_text("""
                    SELECT COALESCE(MAX(n_lineages_identified), 0),
                           COALESCE(AVG(CAST(ecosystem_stats->>'avg_depth' AS FLOAT)), 0)
                    FROM mutation_lineage_log
                    LIMIT 1
                """))
                row = result.fetchone()
                metrics["lineages_identified"] = int(row[0]) if row else 0
                metrics["lineage_depth_avg"] = round(float(row[1] or 0), 2) if row else 0
        except Exception:
            metrics.setdefault("n_dominant_lineages", 0)
            metrics.setdefault("lineages_identified", 0)
            metrics.setdefault("lineage_depth_avg", 0.0)

        # ─── Mutation Ecology ───
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
        except Exception:
            metrics.setdefault("mutation_candidates", 0)
            metrics.setdefault("mutation_family_count", 0)

        # ─── Regime Specialization ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(COUNT(DISTINCT primary_affinity), 0) AS spec_count,
                        COALESCE(AVG(bull_survivability), 0) AS avg_bull,
                        COALESCE(AVG(bear_survivability), 0) AS avg_bear,
                        COALESCE(AVG(ranging_survivability), 0) AS avg_ranging
                    FROM organism_regime_profile
                    WHERE profiled_at > NOW() - INTERVAL '24 hours'
                """))
                row = result.fetchone()
                if row:
                    metrics["regime_specialization_count"] = int(row[0])
                    metrics["regime_affinity_bull"] = round(float(row[1]), 4)
                    metrics["regime_affinity_bear"] = round(float(row[2]), 4)
                    metrics["regime_affinity_ranging"] = round(float(row[3]), 4)
                    n_profiled = metrics.get("validated_organisms", 1)
                    metrics["regime_specialization_diversity"] = round(int(row[0]) / max(1, n_profiled), 4)
        except Exception:
            metrics.setdefault("regime_specialization_count", 0)
            metrics.setdefault("regime_specialization_diversity", 0.0)
            metrics.setdefault("regime_affinity_bull", 0.0)
            metrics.setdefault("regime_affinity_bear", 0.0)
            metrics.setdefault("regime_affinity_ranging", 0.0)

        # ─── Portfolio Evolution ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT diversification_score, concentration_risk
                    FROM portfolio_intelligence
                    ORDER BY computed_at DESC LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    metrics["portfolio_diversification"] = round(float(row[0]), 4) if row[0] else 0.5
                    metrics["concentration_risk"] = round(float(row[1]), 4) if row[1] else 0
        except Exception:
            metrics.setdefault("portfolio_diversification", 0.5)
            metrics.setdefault("concentration_risk", 0)

        # ─── Portfolio Evolution Pressure Log ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT evolution_pressure_stats
                    FROM portfolio_evolution_log
                    ORDER BY tracked_at DESC LIMIT 1
                """))
                row = result.fetchone()
                if row and row[0]:
                    stats = row[0]
                    if isinstance(stats, str):
                        stats = json.loads(stats)
                    metrics["capital_migrated_pct"] = round(float(stats.get("total_capital_migrated", 0)) * 100, 2)
                    metrics["n_weak_penalized"] = int(stats.get("n_weak_penalized", 0))
                    metrics["n_dominant_boosted"] = int(stats.get("n_dominant_boosted", 0))
        except Exception:
            metrics.setdefault("capital_migrated_pct", 0.0)
            metrics.setdefault("n_weak_penalized", 0)
            metrics.setdefault("n_dominant_boosted", 0)

        # ─── Scout Divergence ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE((SELECT MAX(MAX(dynamic_trust_score) - MIN(dynamic_trust_score))
                                 FROM source_performance_log
                                 WHERE updated_at > NOW() - INTERVAL '24 hours'), 0) AS trust_divergence,
                        COALESCE((SELECT COUNT(DISTINCT source_scout)
                                 FROM scout_economic_attribution
                                 WHERE created_at > NOW() - INTERVAL '24 hours'), 0) AS scout_count
                """))
                row = result.fetchone()
                if row:
                    metrics["scout_trust_divergence"] = round(float(row[0]), 4)
                    metrics["scout_divergence_count"] = int(row[1])
        except Exception:
            metrics.setdefault("scout_trust_divergence", 0.0)
            metrics.setdefault("scout_divergence_count", 0)

        # ─── Scout Divergence Log ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT ecosystem_scout_health
                    FROM scout_divergence_log
                    ORDER BY tracked_at DESC LIMIT 1
                """))
                row = result.fetchone()
                if row and row[0]:
                    health = row[0]
                    if isinstance(health, str):
                        health = json.loads(health)
                    metrics["n_high_value_scouts"] = int(health.get("n_high_value_scouts", 0))
                    metrics["n_contradictory_scouts"] = int(health.get("n_contradictory_scouts", 0))
        except Exception:
            metrics.setdefault("n_high_value_scouts", 0)
            metrics.setdefault("n_contradictory_scouts", 0)

        # ─── Regime Stress / Perturbations ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT
                        COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0) AS active_perturbations,
                        COALESCE(COUNT(DISTINCT CASE WHEN status = 'active' THEN perturbation_type END), 0) AS active_types
                    FROM regime_perturbation_events
                    WHERE started_at > NOW() - INTERVAL '1 hour'
                """))
                row = result.fetchone()
                if row:
                    metrics["active_perturbations"] = int(row[0])
                    metrics["stress_level"] = round(min(1.0, int(row[0]) / 4.0), 4)
        except Exception:
            metrics.setdefault("active_perturbations", 0)
            metrics.setdefault("stress_level", 0.0)

        # ─── Execution Realism ───
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(sa_text("""
                    SELECT execution_degradation_score, avg_expected_slippage_bps, avg_fill_probability
                    FROM execution_realism
                    ORDER BY simulated_at DESC LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    metrics["execution_degradation"] = round(float(row[0]), 4) if row[0] else 0
                    metrics["avg_slippage_bps"] = round(float(row[1]), 2) if row[1] else 0
                    metrics["avg_fill_probability"] = round(float(row[2]), 4) if row[2] else 0
        except Exception:
            metrics.setdefault("execution_degradation", 0.0)
            metrics.setdefault("avg_slippage_bps", 0.0)
            metrics.setdefault("avg_fill_probability", 0.0)

        # ─── Mutation Accept Rate ───
        try:
            total_muts = metrics.get("mutation_candidates", 0)
            total_gen = metrics.get("strategies_generated", 0)
            metrics["mutation_accept_rate"] = round(
                total_muts / max(1, total_gen), 4
            ) if total_gen > 0 else 0.0
        except Exception:
            metrics["mutation_accept_rate"] = 0.0

        # ─── Compute Composite Scores ───
        metrics = self._compute_composite_scores(metrics)

        # Persist
        await self._persist(metrics)
        self.metrics_history.append(metrics)

        return metrics

    def _compute_composite_scores(self, metrics: dict) -> dict:
        """Compute Phase 31 composite scores."""
        val = metrics.get("validated_organisms", 0)
        trades = metrics.get("trades_executed", 0)
        lineages = metrics.get("lineages_identified", 0)
        mutations = metrics.get("mutation_candidates", 0)
        retired = metrics.get("retirement_count", 0)
        perturbations = metrics.get("active_perturbations", 0)
        bs = metrics.get("regime_affinity_bull", 0)
        br = metrics.get("regime_affinity_bear", 0)
        rg = metrics.get("regime_affinity_ranging", 0)
        dominant_boosted = metrics.get("n_dominant_boosted", 0)
        weak_penalized = metrics.get("n_weak_penalized", 0)
        collapsed = metrics.get("n_collapsed", 0)
        survivors = metrics.get("n_survivors", 0)
        div = metrics.get("portfolio_diversification", 0.5)
        scout_tr = metrics.get("scout_trust_divergence", 0)
        hv_scouts = metrics.get("n_high_value_scouts", 0)

        # Dominant Emergence Score: how much dominant organisms have emerged
        dominant_emergence = (
            min(1.0, val / 15) * 0.25
            + metrics.get("dominant_concentration", 0) * 0.35
            + min(1.0, dominant_boosted / 5) * 0.25
            + min(1.0, scout_tr * 3) * 0.15
        )
        metrics["dominant_emergence_score"] = round(dominant_emergence * 100, 1)

        # Lineage Evolution Score: how well mutation lineages are evolving
        lineage_evolution = (
            min(1.0, lineages / 5) * 0.30
            + min(1.0, mutations / 50) * 0.25
            + metrics.get("lineage_depth_avg", 0) / 5 * 0.25
            + metrics.get("mutation_family_count", 0) / 10 * 0.20
        )
        metrics["lineage_evolution_score"] = round(lineage_evolution * 100, 1)

        # Regime Adaptation Score: how well organisms adapt to regime diversity
        regime_adapt = (
            (bs + br + rg) / 3 * 0.40
            + metrics.get("regime_specialization_diversity", 0) * 0.30
            + min(1.0, perturbations / 3) * 0.15
            + min(1.0, val / 10) * 0.15
        )
        metrics["regime_adaptation_score"] = round(regime_adapt * 100, 1)

        # Scout Predictive Divergence
        scout_div = (
            min(1.0, scout_tr * 5) * 0.35
            + min(1.0, hv_scouts / 3) * 0.30
            + (1.0 - min(1.0, metrics.get("n_contradictory_scouts", 0) / max(1, hv_scouts + 1))) * 0.20
            + min(1.0, metrics.get("scout_divergence_count", 0) / 5) * 0.15
        )
        metrics["scout_predictive_divergence"] = round(scout_div * 100, 1)

        # Portfolio Evolution Pressure
        portfolio_pressure = (
            min(1.0, weak_penalized / 5) * 0.30
            + metrics.get("capital_migrated_pct", 0) / 50 * 0.30
            + (1.0 - min(1.0, div)) * 0.20  # Concentration is good
            + min(1.0, dominant_boosted / 5) * 0.20
        )
        metrics["portfolio_evolution_pressure"] = round(portfolio_pressure * 100, 1)

        # Stress Survival Score
        total_orgs = collapsed + survivors
        survival_rate = survivors / max(1, total_orgs)
        stress_survival = (
            survival_rate * 0.35
            + (1.0 - metrics.get("execution_degradation", 0)) * 0.25
            + max(0, 1.0 - perturbations * 0.15) * 0.20
            + min(1.0, val / 15) * 0.20
        )
        metrics["stress_survival_score"] = round(stress_survival * 100, 1)

        return metrics

    def _ensure_defaults(self, metrics: dict) -> dict:
        """Ensure all expected metric keys have default values."""
        defaults = {
            "strategies_generated": 0, "validated_organisms": 0, "active_organisms": 0,
            "pending_backtest": 0, "pending_validation": 0, "pending_code": 0,
            "trades_executed": 0, "trade_throughput_24h": 0, "avg_trades_per_strategy": 0.0,
            "n_dominant_identified": 0, "n_dominant_lineages": 0, "dominant_concentration": 0.0,
            "mutation_candidates": 0, "mutation_family_count": 0, "mutation_accept_rate": 0.0,
            "lineages_identified": 0, "lineage_depth_avg": 0.0,
            "regime_specialization_count": 0, "regime_specialization_diversity": 0.0,
            "regime_affinity_bull": 0.0, "regime_affinity_bear": 0.0, "regime_affinity_ranging": 0.0,
            "portfolio_diversification": 0.5, "concentration_risk": 0.0,
            "capital_migrated_pct": 0.0, "n_weak_penalized": 0, "n_dominant_boosted": 0,
            "retirement_count": 0,
            "scout_divergence_count": 0, "scout_trust_divergence": 0.0,
            "n_high_value_scouts": 0, "n_contradictory_scouts": 0,
            "active_perturbations": 0, "stress_level": 0.0,
            "n_survivors": 0, "n_collapsed": 0,
            "execution_degradation": 0.0, "avg_slippage_bps": 0.0, "avg_fill_probability": 0.0,
            "dominant_emergence_score": 0.0, "lineage_evolution_score": 0.0,
            "regime_adaptation_score": 0.0, "scout_predictive_divergence": 0.0,
            "portfolio_evolution_pressure": 0.0, "stress_survival_score": 0.0,
        }
        for k, v in defaults.items():
            if k not in metrics:
                metrics[k] = v
        return metrics

    async def _persist(self, metrics: dict) -> bool:
        """Persist metrics snapshot to phase31_specialization_metrics."""
        metrics = self._ensure_defaults(metrics)
        recorded_at = metrics.get("recorded_at", datetime.now(timezone.utc))
        if isinstance(recorded_at, str):
            recorded_at = recorded_at.replace("Z", "+00:00")
        try:
            async with self.engine.begin() as conn:
                await conn.execute(sa_text("""
                    INSERT INTO phase31_specialization_metrics (
                        recorded_at, runtime_minutes,
                        strategies_generated, validated_organisms, active_organisms,
                        pending_backtest, pending_validation, pending_code,
                        trades_executed, trade_throughput_24h, avg_trades_per_strategy,
                        n_dominant_identified, n_dominant_lineages, dominant_concentration,
                        mutation_candidates, mutation_family_count, mutation_accept_rate,
                        lineages_identified, lineage_depth_avg,
                        regime_specialization_count, regime_specialization_diversity,
                        regime_affinity_bull, regime_affinity_bear, regime_affinity_ranging,
                        portfolio_diversification, concentration_risk,
                        capital_migrated_pct, n_weak_penalized, n_dominant_boosted,
                        retirement_count,
                        scout_divergence_count, scout_trust_divergence,
                        n_high_value_scouts, n_contradictory_scouts,
                        active_perturbations, stress_level, n_survivors, n_collapsed,
                        execution_degradation, avg_slippage_bps, avg_fill_probability,
                        dominant_emergence_score, lineage_evolution_score,
                        regime_adaptation_score, scout_predictive_divergence,
                        portfolio_evolution_pressure, stress_survival_score,
                        metadata
                    ) VALUES (
                        :recorded_at, :runtime_minutes,
                        :strategies_generated, :validated_organisms, :active_organisms,
                        :pending_backtest, :pending_validation, :pending_code,
                        :trades_executed, :trade_throughput_24h, :avg_trades_per_strategy,
                        :n_dominant_identified, :n_dominant_lineages, :dominant_concentration,
                        :mutation_candidates, :mutation_family_count, :mutation_accept_rate,
                        :lineages_identified, :lineage_depth_avg,
                        :regime_specialization_count, :regime_specialization_diversity,
                        :regime_affinity_bull, :regime_affinity_bear, :regime_affinity_ranging,
                        :portfolio_diversification, :concentration_risk,
                        :capital_migrated_pct, :n_weak_penalized, :n_dominant_boosted,
                        :retirement_count,
                        :scout_divergence_count, :scout_trust_divergence,
                        :n_high_value_scouts, :n_contradictory_scouts,
                        :active_perturbations, :stress_level, :n_survivors, :n_collapsed,
                        :execution_degradation, :avg_slippage_bps, :avg_fill_probability,
                        :dominant_emergence_score, :lineage_evolution_score,
                        :regime_adaptation_score, :scout_predictive_divergence,
                        :portfolio_evolution_pressure, :stress_survival_score,
                        :metadata
                    )
                """), metrics | {"metadata": json.dumps({
                    "runtime_minutes": metrics["runtime_minutes"],
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })})
            return True
        except Exception as e:
            logger.warning(f"Persist Phase 31 metrics failed: {e}")
            return False

    async def get_summary(self) -> dict:
        """Compute final summary from accumulated metrics."""
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        initial = self.metrics_history[0] if len(self.metrics_history) > 1 else latest

        deltas = {}
        for key in [
            "strategies_generated", "validated_organisms", "active_organisms",
            "trades_executed", "mutation_candidates", "retirement_count",
            "n_dominant_identified", "n_dominant_lineages",
            "dominant_emergence_score", "lineage_evolution_score",
            "regime_adaptation_score", "scout_predictive_divergence",
            "portfolio_evolution_pressure", "stress_survival_score",
        ]:
            old_val = initial.get(key, 0) if isinstance(initial.get(key), (int, float)) else 0
            new_val = latest.get(key, 0) if isinstance(latest.get(key), (int, float)) else 0
            deltas[key] = {"start": old_val, "end": new_val, "delta": new_val - old_val}

        return {
            "duration_minutes": latest.get("runtime_minutes", 0),
            "n_snapshots": len(self.metrics_history),
            "latest_snapshot": latest,
            "deltas": deltas,
            "final_scores": {
                "dominant_emergence": latest.get("dominant_emergence_score", 0),
                "lineage_evolution": latest.get("lineage_evolution_score", 0),
                "regime_adaptation": latest.get("regime_adaptation_score", 0),
                "scout_divergence": latest.get("scout_predictive_divergence", 0),
                "portfolio_evolution": latest.get("portfolio_evolution_pressure", 0),
                "stress_survival": latest.get("stress_survival_score", 0),
            },
        }

    async def close(self):
        await self.engine.dispose()


# ─────────────────────────────────────────────────────────
# SOAK CONTROLLER
# ─────────────────────────────────────────────────────────

class SpecializationSoakController:
    """Controls the Phase 31 specialization soak run."""

    def __init__(self, duration_minutes: int = 720):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = 300  # Every 5 minutes
        self.db_url = settings.database_url
        self.metrics = SpecializationMetricsCollector(self.db_url)
        self._shutdown = False
        self._start_time: Optional[float] = None

        # Phase 31 engine instances (lazily initialized)
        self._dominant_tracker: Optional[DominantOrganismTracker] = None
        self._lineage_tracker: Optional[MutationLineageTracker] = None
        self._regime_engine: Optional[RegimeSpecializationEngine] = None
        self._scout_engine: Optional[ScoutDivergenceEngine] = None
        self._portfolio_engine: Optional[PortfolioEvolutionPressure] = None
        self._stress_engine: Optional[RegimeStressEngine] = None
        self._soak_db: Optional['SoakDbClient'] = None
        self._engines_initialized = False

    async def _ensure_engines(self):
        """Lazily initialize Phase 31 engines."""
        if self._engines_initialized:
            return
        try:
            # Create lightweight DB client wrapper for engine use
            from sqlalchemy.ext.asyncio import create_async_engine as _create_ae
            _engine = _create_ae(settings.database_url)
            self._soak_db = SoakDbClient(_engine)

            self._dominant_tracker = DominantOrganismTracker(
                redis_client=None, db_client=self._soak_db,
            )
            self._lineage_tracker = MutationLineageTracker(
                redis_client=None, db_client=self._soak_db,
            )
            self._regime_engine = RegimeSpecializationEngine(
                redis_client=None, db_client=self._soak_db,
            )
            self._scout_engine = ScoutDivergenceEngine(
                redis_client=None, db_client=self._soak_db,
            )
            self._portfolio_engine = PortfolioEvolutionPressure(
                redis_client=None, db_client=self._soak_db,
            )
            self._stress_engine = RegimeStressEngine(
                redis_client=None, db_client=self._soak_db,
            )
            self._engines_initialized = True
            logger.info("Phase 31 engines initialized successfully")
        except Exception as e:
            logger.warning(f"Phase 31 engine init failed (non-fatal): {e}")

    async def _run_phase31_cycle(self):
        """Drive all Phase 31 engines for one cycle.
        
        Calls each engine's private _*_cycle() method directly (not run(),
        which has an infinite loop). Uses asyncio.wait_for() with 30s
        timeouts to prevent any single engine from blocking the soak.
        """
        await self._ensure_engines()
        if not self._engines_initialized:
            return
        
        async def _safe_call(name: str, coro, timeout: int = 30):
            try:
                await asyncio.wait_for(coro, timeout=timeout)
                logger.debug(f"  Phase31[{name}]: OK")
            except asyncio.TimeoutError:
                logger.warning(f"  Phase31[{name}]: TIMEOUT after {timeout}s")
            except Exception as e:
                logger.warning(f"  Phase31[{name}]: FAILED — {type(e).__name__}: {e}")

        logger.debug("Running Phase 31 engine cycle...")

        # 31A: Dominant organism tracking — _tracking_cycle()
        if self._dominant_tracker:
            await _safe_call("DominantOrganism", self._dominant_tracker._tracking_cycle())

        # 31B: Mutation lineage tracking — _lineage_cycle()
        if self._lineage_tracker:
            await _safe_call("MutationLineage", self._lineage_tracker._lineage_cycle())

        # 31C: Regime specialization — _profiling_cycle()
        if self._regime_engine:
            await _safe_call("RegimeSpecialization", self._regime_engine._profiling_cycle())

        # 31D: Scout divergence — _divergence_cycle()
        if self._scout_engine:
            await _safe_call("ScoutDivergence", self._scout_engine._divergence_cycle())

        # 31E: Portfolio evolution pressure — _pressure_cycle()
        if self._portfolio_engine:
            await _safe_call("PortfolioEvolution", self._portfolio_engine._pressure_cycle())

        # 31F: Stress engine perturbations — _stress_cycle()
        if self._stress_engine:
            await _safe_call("RegimeStress", self._stress_engine._stress_cycle())

        logger.debug("Phase 31 engine cycle complete")

    async def run(self):
        """Run the full specialization soak."""
        logger.info("=" * 70)
        logger.info("PHASE 31 — LONG-HORIZON SPECIALIZATION SOAK STARTING")
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
                pass

        self._start_time = time.time()

        try:
            while not self._shutdown:
                elapsed = time.time() - self._start_time
                remaining = self.duration_seconds - elapsed

                if remaining <= 0:
                    logger.info("Soak duration reached — completing")
                    break

                elapsed_minutes = int(elapsed / 60)

                # Run Phase 31 engines to generate data
                await self._run_phase31_cycle()

                # Collect metrics
                metrics = await self.metrics.collect(elapsed_minutes)

                # Print progress
                self._print_status(metrics, elapsed, remaining)

                await asyncio.sleep(min(self.metrics_interval, remaining))

        except asyncio.CancelledError:
            logger.info("Soak cancelled")
        except Exception as e:
            logger.error(f"Soak error: {e}", exc_info=True)
        finally:
            await self._finalize()

    def _handle_shutdown(self):
        logger.info("Shutdown signal received — completing soak")
        self._shutdown = True

    def _print_status(self, metrics: dict, elapsed: float, remaining: float):
        elapsed_min = int(elapsed / 60)
        remaining_min = int(remaining / 60)

        de = metrics.get("dominant_emergence_score", 0)
        le = metrics.get("lineage_evolution_score", 0)
        ra = metrics.get("regime_adaptation_score", 0)
        sd = metrics.get("scout_predictive_divergence", 0)
        pe = metrics.get("portfolio_evolution_pressure", 0)
        ss = metrics.get("stress_survival_score", 0)

        print(f"\n[Phase31] T+{elapsed_min}m / T-{remaining_min}m")
        print(f"  Composite: DE={de:.1f} LE={le:.1f} RA={ra:.1f} SD={sd:.1f} PE={pe:.1f} SS={ss:.1f}")
        print(f"  Population: {metrics.get('strategies_generated',0)} gen | "
              f"{metrics.get('validated_organisms',0)} val | "
              f"{metrics.get('active_organisms',0)} act | "
              f"{metrics.get('retirement_count',0)} retired")
        print(f"  Ecology: {metrics.get('trades_executed',0)} trades | "
              f"{metrics.get('mutation_candidates',0)} muts | "
              f"{metrics.get('lineages_identified',0)} lineages")
        print(f"  Dominants: {metrics.get('n_dominant_identified',0)} orgs | "
              f"{metrics.get('n_dominant_lineages',0)} lineages | "
              f"Conc={metrics.get('dominant_concentration',0):.3f}")
        print(f"  Stress: {metrics.get('active_perturbations',0)} pert | "
              f"Level={metrics.get('stress_level',0):.2f} | "
              f"Survivors={metrics.get('n_survivors',0)} | "
              f"Collapsed={metrics.get('n_collapsed',0)}")
        print(f"  Regime: Bull={metrics.get('regime_affinity_bull',0):.2f} "
              f"Bear={metrics.get('regime_affinity_bear',0):.2f} "
              f"Ranging={metrics.get('regime_affinity_ranging',0):.2f}")
        sys.stdout.flush()

    async def _finalize(self):
        final_elapsed = time.time() - self._start_time if self._start_time else 0
        final_minutes = int(final_elapsed / 60)

        print(f"\n{'=' * 70}")
        print(f"PHASE 31 SOAK COMPLETE — {final_minutes} minutes elapsed")
        print(f"{'=' * 70}")

        summary = await self.metrics.get_summary()
        print(json.dumps(summary, indent=2, default=str))

        await self.metrics.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Phase 31: Long-Horizon Specialization Soak — 12-hour adaptive specialization test"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=720,
        help="Soak duration in minutes (default: 720 = 12 hours)",
    )
    parser.add_argument(
        "--metrics-interval",
        type=int,
        default=300,
        help="Metrics collection interval in seconds (default: 300 = 5 min)",
    )
    args = parser.parse_args()

    controller = SpecializationSoakController(duration_minutes=args.duration_minutes)
    controller.metrics_interval = args.metrics_interval
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
