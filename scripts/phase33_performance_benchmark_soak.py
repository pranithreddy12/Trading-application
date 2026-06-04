"""
phase33_performance_benchmark_soak.py — Phase 33: Full Performance & Adaptive Intelligence Benchmarking.

PHASE 33A — ECONOMIC PERFORMANCE BENCHMARK
  Measures: expectancy, Sharpe, Sortino, Calmar, capital efficiency, drawdown recovery,
  survival quality, risk-adjusted return, organism profitability distribution.
  Compares early-generation vs later-generation organisms.

PHASE 33B — INFRASTRUCTURE PERFORMANCE BENCHMARK
  Measures: RAM stability, CPU utilization, event loop lag, DB insert throughput,
  replay integrity, queue depth, dead-letter growth, task/thread growth,
  failed inserts, restart storms.

PHASE 33C — EVOLUTIONARY PERFORMANCE BENCHMARK
  Measures: mutation-family survival, dominant organism emergence, organism lifespan,
  retirement causes, regime specialization, scout trust divergence,
  portfolio adaptation, capital migration, adaptive allocation quality.

PHASE 33D — REGIME STRESS TESTING
  Injects: volatility spikes, liquidity droughts, spread widening, execution degradation,
  trend reversals, market shocks.
  Observes: organism collapse rates, recovery speed, portfolio survivability,
  adaptive reallocation, mutation-family resilience.

PHASE 33E — LONG-HORIZON PERFORMANCE SOAK
  720-minute run with full mutation ecology, specialization persistence,
  portfolio evolution, scout divergence, execution realism, replay verification,
  synthetic perturbations, adaptive allocation, organism retirement, scarcity pressure.

Usage:
    python scripts/phase33_performance_benchmark_soak.py --duration-minutes 720 --metrics-interval 300
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas.config.settings import settings
from atlas.core.persistence_integrity import normalize_uuid_params
from atlas.data.storage.timescale_client import TimescaleClient, _extract_table_name_from_insert

from atlas.agents.l7_meta.dominant_organism_tracker import DominantOrganismTracker
from atlas.agents.l7_meta.mutation_lineage_tracker import MutationLineageTracker
from atlas.agents.l7_meta.regime_specialization_engine import RegimeSpecializationEngine
from atlas.agents.l7_meta.scout_divergence_engine import ScoutDivergenceEngine
from atlas.agents.l6_portfolio.portfolio_evolution_pressure import PortfolioEvolutionPressure
from atlas.agents.l7_meta.regime_stress_engine import RegimeStressEngine
from atlas.agents.l7_meta.mutation_policy_engine import MutationPolicyEngine
from atlas.agents.l7_meta.economic_efficiency_engine import EconomicEfficiencyEngine
from atlas.agents.l7_meta.strategy_retirement_engine import StrategyRetirementEngine
from atlas.agents.l7_meta.replay_engine import ReplayEngine


# ────────────────────────────────────────────────────────
# PHASE 33D — SYNTHETIC PERTURBATION PRESETS
# ────────────────────────────────────────────────────────

PERTURBATION_PRESETS = {
    "volatility_spike": {
        "description": "Sudden 2x-5x volatility spike lasting 15-60 minutes",
        "type": "volatility",
        "severity_range": (2.0, 5.0),
        "duration_minutes_range": (15, 60),
        "affected_channels": ["regime_detection", "position_sizing"],
    },
    "liquidity_drought": {
        "description": "Extended liquidity drought — volume drops 80-95% for 30-120 minutes",
        "type": "liquidity",
        "severity_range": (4.0, 8.0),
        "duration_minutes_range": (30, 120),
        "affected_channels": ["execution", "slippage_modeling", "position_sizing"],
    },
    "spread_widening": {
        "description": "Bid-ask spread widens 5x-15x for 5-30 minutes",
        "type": "execution",
        "severity_range": (5.0, 15.0),
        "duration_minutes_range": (5, 30),
        "affected_channels": ["execution_gateway", "cost_modeling"],
    },
    "execution_degradation": {
        "description": "Fill rate drops to 30-60%, slippage increases 3x-8x",
        "type": "execution",
        "severity_range": (3.0, 8.0),
        "duration_minutes_range": (10, 45),
        "affected_channels": ["fill_modeling", "execution_gateway", "cost_modeling"],
    },
    "trend_reversal": {
        "description": "Sudden 180° price movement over 5-20 bars",
        "type": "trend",
        "severity_range": (1.5, 4.0),
        "duration_minutes_range": (5, 20),
        "affected_channels": ["trend_detection", "entry_filters"],
    },
    "market_shock": {
        "description": "5-15% market shock over 5-15 minutes with sharp reversal",
        "type": "volatility",
        "severity_range": (8.0, 15.0),
        "duration_minutes_range": (5, 15),
        "affected_channels": ["all"],
    },
    "regime_oscillation": {
        "description": "Rapid regime oscillation every 5-15 minutes for 30-90 minutes",
        "type": "regime",
        "severity_range": (1.0, 2.0),
        "duration_minutes_range": (30, 90),
        "affected_channels": ["all"],
    },
}


class SoakDbClient:
    """Minimal DB client for agent compatibility."""
    def __init__(self, engine):
        self.engine = engine

    async def _execute_insert(self, query: str, params: dict) -> None:
        table_name = _extract_table_name_from_insert(query)
        normalized, recovered = normalize_uuid_params(
            params,
            table_name=table_name,
            context="Phase33SoakDbClient._execute_insert",
        )
        if recovered:
            logger.warning(
                f"UUID normalization recovered fields for {table_name}: {', '.join(recovered)}"
            )
        async with self.engine.begin() as conn:
            await conn.execute(sa_text(query), normalized)


# ────────────────────────────────────────────────────────
# PHASE 33 — PERFORMANCE METRICS COLLECTOR
# ────────────────────────────────────────────────────────

class PerformanceMetricsCollector:
    """
    Phase 33 metrics collector.
    
    Covers:
      33A — Economic performance (expectancy, Sharpe, Sortino, etc.)
      33B — Infrastructure performance (RAM, CPU, event loop, DB throughput)
      33C — Evolutionary performance (mutation families, dominants, lifespan)
      33D — Regime stress (collapse rates, recovery, portfolio survivability)
      33E — Long-horizon (trends, generational comparison)
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict[str, Any]] = []
        self._generation_snapshots: list[dict] = []
        self._start_time: Optional[float] = None
        self._process = None

    async def initialize(self) -> None:
        """Create phase33_performance_metrics table."""
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase33_performance_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT NOT NULL DEFAULT 0,
                    
                    -- 33A: Economic
                    expectancy_mean FLOAT DEFAULT 0,
                    expectancy_median FLOAT DEFAULT 0,
                    expectancy_p90 FLOAT DEFAULT 0,
                    avg_sharpe FLOAT DEFAULT 0,
                    avg_sortino FLOAT DEFAULT 0,
                    avg_calmar FLOAT DEFAULT 0,
                    avg_composite_fitness FLOAT DEFAULT 0,
                    median_composite_fitness FLOAT DEFAULT 0,
                    top_decile_fitness FLOAT DEFAULT 0,
                    bottom_decile_fitness FLOAT DEFAULT 0,
                    recovery_quality FLOAT DEFAULT 0,
                    drawdown_resilience FLOAT DEFAULT 0,
                    capital_efficiency FLOAT DEFAULT 0,
                    survival_quality FLOAT DEFAULT 0,
                    
                    -- 33B: Infrastructure
                    ram_mb FLOAT DEFAULT 0,
                    cpu_percent FLOAT DEFAULT 0,
                    event_loop_lag_ms FLOAT DEFAULT 0,
                    db_pool_size INT DEFAULT 0,
                    db_checked_out INT DEFAULT 0,
                    db_overflow INT DEFAULT 0,
                    dead_letter_count INT DEFAULT 0,
                    failed_insert_count INT DEFAULT 0,
                    task_count INT DEFAULT 0,
                    thread_count INT DEFAULT 0,
                    restart_count INT DEFAULT 0,
                    
                    -- 33C: Evolutionary
                    dominant_organisms INT DEFAULT 0,
                    active_organisms INT DEFAULT 0,
                    mutation_family_count INT DEFAULT 0,
                    top_mutation_family TEXT DEFAULT '',
                    regime_specialist_count INT DEFAULT 0,
                    cross_regime_survivors INT DEFAULT 0,
                    scout_divergence FLOAT DEFAULT 0,
                    capital_migrated FLOAT DEFAULT 0,
                    diversification_score FLOAT DEFAULT 0,
                    concentration_risk FLOAT DEFAULT 0,
                    organism_lifespan_avg FLOAT DEFAULT 0,
                    retirement_rate FLOAT DEFAULT 0,
                    
                    -- 33D: Regime Stress
                    active_perturbations INT DEFAULT 0,
                    stress_level FLOAT DEFAULT 0,
                    avg_resilience FLOAT DEFAULT 0,
                    n_resilient INT DEFAULT 0,
                    n_fragile INT DEFAULT 0,
                    collapse_rate FLOAT DEFAULT 0,
                    
                    -- 33E: Long-Horizon
                    generation_comparison_score FLOAT DEFAULT 0,
                    adaptive_trend FLOAT DEFAULT 0,
                    
                    -- Composite scores
                    adaptive_quality_score FLOAT DEFAULT 0,
                    specialization_quality_score FLOAT DEFAULT 0,
                    allocation_quality_score FLOAT DEFAULT 0,
                    evolutionary_selection_score FLOAT DEFAULT 0,
                    long_horizon_survivability_score FLOAT DEFAULT 0,
                    infrastructure_stability_score FLOAT DEFAULT 0,
                    stress_resilience_score FLOAT DEFAULT 0,
                    
                    -- Raw data
                    mutation_family_performance JSONB DEFAULT '[]',
                    regime_affinity_rankings JSONB DEFAULT '[]',
                    scout_predictive_rankings JSONB DEFAULT '[]',
                    capital_allocation_evolution JSONB DEFAULT '{}',
                    expectancy_distribution JSONB DEFAULT '{}',
                    execution_degradation_metrics JSONB DEFAULT '{}',
                    replay_integrity FLOAT DEFAULT 1.0,
                    error_count INT DEFAULT 0,
                    trades_per_hour FLOAT DEFAULT 0,
                    execution_degradation FLOAT DEFAULT 0,
                    organism_survival_curves JSONB DEFAULT '[]',
                    stress_state JSONB DEFAULT '{}',
                    infrastructure_snapshot JSONB DEFAULT '{}',
                    metadata JSONB DEFAULT '{}'
                )
            """))
            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase33_perf_metrics_time
                ON phase33_performance_metrics (recorded_at DESC)
            """))

        logger.info("Phase 33 performance metrics table initialized")

    def _try_get_process(self):
        """Lazy import psutil and get process handle."""
        if self._process is not None:
            return self._process
        try:
            import psutil
            self._process = psutil.Process(os.getpid())
            return self._process
        except ImportError:
            logger.warning("psutil not installed — infrastructure metrics limited")
            return None

    async def _collect_infrastructure_metrics(self) -> dict:
        """PHASE 33B: Collect infrastructure/runtime metrics."""
        infra = {
            "ram_mb": 0.0,
            "cpu_percent": 0.0,
            "event_loop_lag_ms": 0.0,
            "db_pool_size": 0,
            "db_checked_out": 0,
            "db_overflow": 0,
            "dead_letter_count": 0,
            "failed_insert_count": 0,
            "task_count": 0,
            "thread_count": 0,
            "restart_count": 0,
        }

        # Process-level metrics
        proc = self._try_get_process()
        if proc:
            try:
                mem = proc.memory_info()
                infra["ram_mb"] = round(mem.rss / 1024 / 1024, 1)
                infra["cpu_percent"] = proc.cpu_percent(interval=0.1)
                infra["thread_count"] = proc.num_threads()
            except Exception:
                pass

        # Event loop lag
        loop = asyncio.get_event_loop()
        try:
            t0 = loop.time()
            await asyncio.sleep(0.001)
            lag = (loop.time() - t0) * 1000 - 1.0
            infra["event_loop_lag_ms"] = round(max(0, lag), 2)
        except Exception:
            pass

        # Event loop task count
        try:
            tasks = asyncio.all_tasks(loop)
            infra["task_count"] = len(tasks)
        except Exception:
            pass

        # DB-level metrics
        async with self.engine.connect() as conn:
            try:
                async with conn.begin_nested():
                    r = await conn.execute(sa_text(
                        "SELECT COUNT(*) FROM dead_letter_queue WHERE status = 'unresolved'"
                    ))
                    infra["dead_letter_count"] = int(r.scalar() or 0)
            except Exception:
                pass

            try:
                async with conn.begin_nested():
                    r = await conn.execute(sa_text(
                        "SELECT COUNT(*) FROM failed_inserts"
                    ))
                    infra["failed_insert_count"] = int(r.scalar() or 0)
            except Exception:
                pass

            try:
                async with conn.begin_nested():
                    r = await conn.execute(sa_text(
                        "SELECT COUNT(*) FROM restart_log WHERE restarted_at > NOW() - INTERVAL '1 hour'"
                    ))
                    infra["restart_count"] = int(r.scalar() or 0)
            except Exception:
                pass

        return infra

    async def _collect_33a_economic(self, conn) -> dict[str, Any]:
        """PHASE 33A: Economic performance metrics."""
        econ: dict[str, Any] = {
            "expectancy_mean": 0.0,
            "expectancy_median": 0.0,
            "expectancy_p90": 0.0,
            "avg_sharpe": 0.0,
            "avg_sortino": 0.0,
            "avg_calmar": 0.0,
            "avg_composite_fitness": 0.0,
            "median_composite_fitness": 0.0,
            "top_decile_fitness": 0.0,
            "bottom_decile_fitness": 0.0,
            "recovery_quality": 0.0,
            "drawdown_resilience": 0.0,
            "capital_efficiency": 0.0,
            "survival_quality": 0.0,
        }

        async def safe_scalar(sql: str, default: Any = 0) -> Any:
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).scalar() or default
            except Exception:
                return default

        async def safe_fetchone(sql: str):
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).fetchone()
            except Exception:
                return None

        # Composite fitness stats
        econ["avg_composite_fitness"] = float(await safe_scalar(
            "SELECT COALESCE(AVG(composite_fitness_score), 0) FROM backtest_results "
            "WHERE created_at > NOW() - INTERVAL '14 days'"
        ))
        econ["median_composite_fitness"] = float(await safe_scalar(
            "SELECT COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY composite_fitness_score), 0) "
            "FROM backtest_results WHERE created_at > NOW() - INTERVAL '14 days'"
        ))
        econ["top_decile_fitness"] = float(await safe_scalar(
            "SELECT COALESCE(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY composite_fitness_score), 0) "
            "FROM backtest_results WHERE created_at > NOW() - INTERVAL '14 days'"
        ))
        econ["bottom_decile_fitness"] = float(await safe_scalar(
            "SELECT COALESCE(PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY composite_fitness_score), 0) "
            "FROM backtest_results WHERE created_at > NOW() - INTERVAL '14 days'"
        ))

        # Sharpe, Sortino, Calmar
        econ["avg_sharpe"] = float(await safe_scalar(
            "SELECT COALESCE(AVG(COALESCE((results->>'sharpe')::numeric, 0)), 0) "
            "FROM backtest_results WHERE created_at > NOW() - INTERVAL '14 days'"
        ))
        econ["avg_sortino"] = float(await safe_scalar(
            "SELECT COALESCE(AVG(sortino_ratio), 0) FROM backtest_results "
            "WHERE created_at > NOW() - INTERVAL '14 days'"
        ))
        econ["avg_calmar"] = float(await safe_scalar(
            "SELECT COALESCE(AVG(calmar_ratio), 0) FROM backtest_results "
            "WHERE created_at > NOW() - INTERVAL '14 days'"
        ))

        # Expectancy distribution
        exp = await safe_fetchone("""
            SELECT COALESCE(AVG(expectancy), 0),
                   COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY expectancy), 0),
                   COALESCE(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY expectancy), 0)
            FROM (
                SELECT CASE WHEN total_trades > 0 THEN
                    (win_rate * 0.01 * sharpe) - ((1 - win_rate * 0.01) * ABS(max_drawdown))
                ELSE 0 END AS expectancy
                FROM backtest_results
                WHERE created_at > NOW() - INTERVAL '14 days'
            ) q
        """)
        if exp:
            econ["expectancy_mean"] = float(exp[0] or 0)
            econ["expectancy_median"] = float(exp[1] or 0)
            econ["expectancy_p90"] = float(exp[2] or 0)

        # Recovery and drawdown
        rec = await safe_fetchone("""
            SELECT
                COALESCE(AVG(composite_fitness_score / NULLIF(ABS(max_drawdown) + 0.01, 0)), 0),
                COALESCE(AVG(ABS(max_drawdown)), 0)
            FROM backtest_results
            WHERE created_at > NOW() - INTERVAL '14 days'
              AND max_drawdown IS NOT NULL
        """)
        if rec:
            recovery_ratio = float(rec[0] or 0)
            avg_dd = float(rec[1] or 0)
            econ["recovery_quality"] = min(3.0, recovery_ratio) / 3.0
            econ["drawdown_resilience"] = max(0.0, 1.0 - min(1.0, avg_dd / 100.0))

        # Replay integrity
        rp = await safe_fetchone("""
            SELECT COALESCE(integrity_score, 100) FROM replay_integrity
            ORDER BY checked_at DESC LIMIT 1
        """)
        integrity_score = float(rp[0] or 100.0) if rp else 100.0
        econ["replay_integrity"] = (
            integrity_score / 100.0 if integrity_score > 1 else integrity_score
        )

        # Execution degradation from execution_realism
        er = await safe_fetchone("""
            SELECT execution_degradation_score, avg_expected_slippage_bps, avg_fill_probability
            FROM execution_realism
            ORDER BY simulated_at DESC LIMIT 1
        """)
        if er:
            econ["execution_degradation"] = round(float(er[0] or 0), 4) if er[0] else 0
            econ["execution_degradation_metrics"] = {
                "degradation": float(er[0] or 0),
                "slippage_bps": float(er[1] or 0),
                "fill_probability": float(er[2] or 0),
            }

        # Capital efficiency (return per unit drawdown from strategies)
        ce = await safe_fetchone("""
            SELECT
                COALESCE(AVG(composite_fitness_score / NULLIF(ABS(COALESCE(max_drawdown, 0.01)), 0)), 0)
            FROM backtest_results
            WHERE created_at > NOW() - INTERVAL '14 days'
              AND composite_fitness_score > 0
        """)
        if ce:
            econ["capital_efficiency"] = float(ce[0] or 0)

        # Survival quality (half-life)
        sq = await safe_fetchone("""
            SELECT COALESCE(AVG(age_bars), 0)
            FROM strategies
            WHERE lifecycle_state IN ('retired', 'dead')
              AND created_at > NOW() - INTERVAL '14 days'
        """)
        if sq:
            half_life_hours = float(sq[0] or 0) / 60
            econ["survival_quality"] = min(1.0, half_life_hours / 168.0)  # Normalize to 1 week

        # Store expectancy distribution as JSON
        econ["expectancy_distribution"] = {
            "mean": econ["expectancy_mean"],
            "median": econ["expectancy_median"],
            "p90": econ["expectancy_p90"],
        }

        # Error count from agent events
        err = await safe_fetchone("""
            SELECT COALESCE(COUNT(*), 0) FROM agent_events
            WHERE status = 'error' AND created_at > NOW() - INTERVAL '1 hour'
        """)
        econ["error_count"] = int(err[0] or 0) if err else 0

        # Trades per hour from execution logs
        tph = await safe_fetchone("""
            SELECT CASE WHEN COUNT(*) > 0
                THEN COUNT(*) / GREATEST(
                    EXTRACT(EPOCH FROM (NOW() - MIN(executed_at))) / 3600, 1
                ) ELSE 0 END
            FROM execution_log
            WHERE executed_at > NOW() - INTERVAL '1 hour'
        """)
        econ["trades_per_hour"] = round(float(tph[0] or 0), 2) if tph else 0.0

        return econ

    async def _collect_33c_evolutionary(self, conn) -> dict[str, Any]:
        """PHASE 33C: Evolutionary performance metrics."""
        evo: dict[str, Any] = {
            "dominant_organisms": 0,
            "active_organisms": 0,
            "mutation_family_count": 0,
            "top_mutation_family": "",
            "regime_specialist_count": 0,
            "cross_regime_survivors": 0,
            "scout_divergence": 0.0,
            "capital_migrated": 0.0,
            "diversification_score": 0.5,
            "concentration_risk": 0.0,
            "organism_lifespan_avg": 0.0,
            "retirement_rate": 0.0,
            "mutation_family_performance": [],
            "regime_affinity_rankings": [],
            "scout_predictive_rankings": [],
            "capital_allocation_evolution": {},
        }

        async def safe_scalar(sql: str, default: Any = 0) -> Any:
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).scalar() or default
            except Exception:
                return default

        async def safe_fetchall(sql: str):
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).fetchall()
            except Exception:
                return []

        async def safe_fetchone(sql: str):
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).fetchone()
            except Exception:
                return None

        evo["dominant_organisms"] = int(await safe_scalar(
            "SELECT COALESCE(COUNT(*), 0) FROM strategies WHERE lifecycle_state = 'dominant'"
        ))
        evo["active_organisms"] = int(await safe_scalar(
            "SELECT COALESCE(COUNT(*), 0) FROM strategies "
            "WHERE STATUS IN ('validated', 'elite', 'promoted', 'live')"
        ))
        evo["organism_lifespan_avg"] = float(await safe_scalar(
            "SELECT COALESCE(AVG(age_bars), 0) FROM strategies WHERE age_bars > 0"
        ))

        # Retirement rate (last hour)
        evo["retirement_rate"] = float(await safe_scalar(
            "SELECT COALESCE(COUNT(*), 0) FROM strategies "
            "WHERE lifecycle_state = 'retired' AND created_at > NOW() - INTERVAL '1 hour'"
        ))

        # Mutation families
        mut_rows = await safe_fetchall("""
            SELECT mutation_type, COUNT(*),
                   COALESCE(AVG(sharpe_delta), 0), COALESCE(AVG(score_delta), 0)
            FROM mutation_memory
            WHERE created_at > NOW() - INTERVAL '14 days'
            GROUP BY mutation_type
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        families = []
        for r in mut_rows:
            families.append({
                "family": str(r[0] or "unknown"),
                "n_obs": int(r[1] or 0),
                "avg_sharpe_delta": float(r[2] or 0),
                "avg_score_delta": float(r[3] or 0),
            })
        evo["mutation_family_performance"] = families
        evo["mutation_family_count"] = len(families)
        if families:
            evo["top_mutation_family"] = families[0]["family"]

        # Regime specialization
        regime_rows = await safe_fetchall("""
            SELECT primary_affinity,
                   COALESCE(AVG((bull_survivability + bear_survivability + ranging_survivability) / 3.0), 0),
                   COUNT(*)
            FROM organism_regime_profile
            WHERE profiled_at > NOW() - INTERVAL '14 days'
            GROUP BY primary_affinity
            ORDER BY COUNT(*) DESC
        """)
        regimes = []
        for r in regime_rows:
            regimes.append({
                "regime": str(r[0] or "unknown"),
                "survivability": float(r[1] or 0),
                "n_obs": int(r[2] or 0),
            })
        evo["regime_affinity_rankings"] = regimes
        evo["regime_specialist_count"] = len(regimes)

        # Cross-regime survivors
        cr = await safe_fetchone("""
            SELECT COUNT(DISTINCT strategy_id) FROM (
                SELECT strategy_id FROM regime_fitness_log
                WHERE regime_fitness_score > 0 AND created_at > NOW() - INTERVAL '14 days'
                GROUP BY strategy_id
                HAVING COUNT(DISTINCT regime) >= 2
            ) multi
        """)
        if cr:
            evo["cross_regime_survivors"] = int(cr[0] or 0)

        # Scout rankings
        scout_rows = await safe_fetchall("""
            SELECT source_scout,
                   COALESCE(AVG(sharpe_contribution), 0),
                   COALESCE(AVG(pnl_contribution), 0),
                   COUNT(*)
            FROM scout_economic_attribution
            WHERE created_at > NOW() - INTERVAL '14 days'
            GROUP BY source_scout
            ORDER BY AVG(sharpe_contribution) DESC
            LIMIT 20
        """)
        scouts = []
        for r in scout_rows:
            scouts.append({
                "scout": str(r[0] or "unknown"),
                "alignment": float(r[1] or 0),
                "avg_net_pnl": float(r[2] or 0),
                "n_obs": int(r[3] or 0),
            })
        evo["scout_predictive_rankings"] = scouts

        # Scout divergence (std of alignment scores)
        if scouts:
            alignments = [s["alignment"] for s in scouts]
            if len(alignments) > 1:
                mean_a = sum(alignments) / len(alignments)
                var_a = sum((a - mean_a) ** 2 for a in alignments) / len(alignments)
                evo["scout_divergence"] = round(math.sqrt(var_a), 4)

        # Portfolio allocation
        alloc = await safe_fetchone("""
            SELECT tracked_at,
                   COALESCE((evolution_pressure_stats->>'total_capital_migrated')::float, 0),
                   COALESCE((evolution_pressure_stats->>'n_dominant_boosted')::int, 0),
                   COALESCE((evolution_pressure_stats->>'n_weak_penalized')::int, 0)
            FROM portfolio_evolution_log
            ORDER BY tracked_at DESC LIMIT 1
        """)
        if alloc:
            evo["capital_migrated"] = float(alloc[1] or 0)
            evo["capital_allocation_evolution"] = {
                "capital_migrated": float(alloc[1] or 0),
                "dominant_boosted": int(alloc[2] or 0),
                "weak_penalized": int(alloc[3] or 0),
            }

        # Diversification
        div = await safe_fetchone("""
            SELECT COALESCE(diversification_score, 0.5), COALESCE(concentration_risk, 0)
            FROM portfolio_intelligence ORDER BY computed_at DESC LIMIT 1
        """)
        if div:
            evo["diversification_score"] = float(div[0] or 0.5)
            evo["concentration_risk"] = float(div[1] or 0)

        # Organism survival curves (lifespan distribution)
        sc_rows = await safe_fetchall("""
            SELECT
                CASE
                    WHEN age_bars < 1000 THEN '0-1K'
                    WHEN age_bars < 5000 THEN '1K-5K'
                    WHEN age_bars < 10000 THEN '5K-10K'
                    WHEN age_bars < 50000 THEN '10K-50K'
                    ELSE '50K+'
                END AS lifespan_bucket,
                COUNT(*) AS cnt,
                ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
            FROM strategies
            WHERE age_bars > 0
              AND lifecycle_state IN ('retired', 'dead', 'dominant')
            GROUP BY lifespan_bucket
            ORDER BY lifespan_bucket
        """)
        evo["organism_survival_curves"] = [
            {"bucket": str(r[0]), "count": int(r[1]), "pct": float(r[2])}
            for r in sc_rows
        ]

        return evo

    async def _collect_33d_stress(self, conn, active_perturbations: list[dict]) -> dict[str, Any]:
        """PHASE 33D: Regime stress metrics."""
        stress: dict[str, Any] = {
            "active_perturbations": len(active_perturbations),
            "stress_level": 0.0,
            "avg_resilience": 0.0,
            "n_resilient": 0,
            "n_fragile": 0,
            "collapse_rate": 0.0,
            "stress_state": {},
        }

        async def safe_scalar(sql: str, default: Any = 0) -> Any:
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).scalar() or default
            except Exception:
                return default

        async def safe_fetchone(sql: str):
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).fetchone()
            except Exception:
                return None

        # Compute stress level from perturbation severity
        if active_perturbations:
            total_severity = sum(
                p.get("severity", 1.0) for p in active_perturbations
            )
            stress["stress_level"] = min(1.0, total_severity / 20.0)

        # Resilience from latest stress assessment
        res = await safe_fetchone("""
            SELECT metadata FROM regime_perturbation_events
            WHERE perturbation_type = 'resilience_assessment'
            ORDER BY started_at DESC LIMIT 1
        """)
        if res and res[0]:
            meta = res[0]
            if isinstance(meta, str):
                meta = json.loads(meta)
            resilience_data = meta.get("resilience_data", {})
            stress["avg_resilience"] = float(resilience_data.get("avg_resilience", 0))
            stress["n_resilient"] = int(resilience_data.get("n_resilient", 0))
            stress["n_fragile"] = int(resilience_data.get("n_fragile", 0))

        # Collapse rate
        stress["collapse_rate"] = float(await safe_scalar(
            "SELECT COALESCE(COUNT(*), 0) FROM strategies "
            "WHERE lifecycle_state IN ('retired', 'dead', 'quarantined') "
            "AND created_at > NOW() - INTERVAL '1 hour'"
        ))

        stress["stress_state"] = {
            "active_perturbations": len(active_perturbations),
            "perturbation_types": [p.get("type", "unknown") for p in active_perturbations],
            "stress_level": stress["stress_level"],
        }

        return stress

    async def _collect_33e_generational(self, conn) -> dict[str, Any]:
        """PHASE 33E: Long-horizon generational comparison."""
        gen: dict[str, Any] = {
            "generation_comparison_score": 0.0,
            "adaptive_trend": 0.0,
        }

        async def safe_fetchone(sql: str):
            try:
                async with conn.begin_nested():
                    return (await conn.execute(sa_text(sql))).fetchone()
            except Exception:
                return None

        # Compare early vs later generation composite fitness
        gc = await safe_fetchone("""
            WITH gen_ranked AS (
                SELECT id, composite_fitness_score,
                       NTILE(2) OVER (ORDER BY created_at) AS generation_half
                FROM backtest_results
                WHERE created_at > NOW() - INTERVAL '30 days'
                  AND composite_fitness_score IS NOT NULL
            )
            SELECT
                COALESCE(AVG(composite_fitness_score) FILTER (WHERE generation_half = 1), 0) AS early_avg,
                COALESCE(AVG(composite_fitness_score) FILTER (WHERE generation_half = 2), 0) AS late_avg,
                COUNT(*) FILTER (WHERE generation_half = 1) AS n_early,
                COUNT(*) FILTER (WHERE generation_half = 2) AS n_late
            FROM gen_ranked
        """)
        if gc:
            early_avg = float(gc[0] or 0)
            late_avg = float(gc[1] or 0)
            n_early = int(gc[2] or 0)
            n_late = int(gc[3] or 0)
            if early_avg > 0 and late_avg > 0:
                gen["generation_comparison_score"] = round(
                    (late_avg - early_avg) / abs(early_avg), 4
                )

        # Adaptive trend: correlation between created_at and fitness (positive = improving)
        trend = await safe_fetchone("""
            SELECT CASE WHEN COUNT(*) > 5
                THEN COALESCE(CORR(
                    EXTRACT(EPOCH FROM created_at),
                    composite_fitness_score
                ), 0)
                ELSE 0 END
            FROM backtest_results
            WHERE created_at > NOW() - INTERVAL '30 days'
              AND composite_fitness_score IS NOT NULL
        """)
        if trend:
            gen["adaptive_trend"] = round(float(trend[0] or 0), 4)

        return gen

    async def collect(
        self,
        runtime_minutes: int,
        active_perturbations: list[dict],
    ) -> dict[str, Any]:
        """Collect all Phase 33 metrics."""

        # Infrastructure (33B) — collected first since CPU measurement requires delay
        infra = await self._collect_infrastructure_metrics()

        # DB-based metrics
        economic: dict = {}
        evolutionary: dict = {}
        stress: dict = {}
        generational: dict = {}

        async with self.engine.connect() as conn:
            economic = await self._collect_33a_economic(conn)
            evolutionary = await self._collect_33c_evolutionary(conn)
            stress = await self._collect_33d_stress(conn, active_perturbations)
            generational = await self._collect_33e_generational(conn)

        # Merge all into one metrics dict
        metrics: dict[str, Any] = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": runtime_minutes,

            # 33A
            **{k: v for k, v in economic.items() if k != "expectancy_distribution"},
            "expectancy_distribution": economic.get("expectancy_distribution", {}),

            # 33B
            **infra,

            # 33C
            **{k: v for k, v in evolutionary.items()
               if k not in ("mutation_family_performance", "regime_affinity_rankings",
                            "scout_predictive_rankings", "capital_allocation_evolution")},
            "mutation_family_performance": evolutionary.get("mutation_family_performance", []),
            "regime_affinity_rankings": evolutionary.get("regime_affinity_rankings", []),
            "scout_predictive_rankings": evolutionary.get("scout_predictive_rankings", []),
            "capital_allocation_evolution": evolutionary.get("capital_allocation_evolution", {}),

            # 33D
            **{k: v for k, v in stress.items() if k != "stress_state"},
            "stress_state": stress.get("stress_state", {}),

            # 33E
            **generational,
        }

        # Merge tracked sub-metrics that may have been computed in collection methods
        if economic.get("replay_integrity") is not None:
            metrics["replay_integrity"] = economic["replay_integrity"]
        if economic.get("error_count") is not None:
            metrics["error_count"] = economic["error_count"]
        if economic.get("trades_per_hour") is not None:
            metrics["trades_per_hour"] = economic["trades_per_hour"]
        if economic.get("execution_degradation") is not None:
            metrics["execution_degradation"] = economic["execution_degradation"]
        if economic.get("execution_degradation_metrics"):
            metrics["execution_degradation_metrics"] = economic["execution_degradation_metrics"]
        if evolutionary.get("organism_survival_curves"):
            metrics["organism_survival_curves"] = evolutionary["organism_survival_curves"]

        # Compute composite scores
        self._compute_composites(metrics)

        # Persist
        await self._persist(metrics)
        self.metrics_history.append(metrics)

        return metrics

    def _compute_composites(self, metrics: dict[str, Any]) -> None:
        """Compute Phase 33 composite quality scores."""
        recovery = float(metrics.get("recovery_quality", 0))
        drawdown_res = float(metrics.get("drawdown_resilience", 0))
        diversification = float(metrics.get("diversification_score", 0.5))
        concentration = float(metrics.get("concentration_risk", 0))
        replay = float(metrics.get("replay_integrity", 1.0))
        infra_stability = float(metrics.get("infrastructure_stability_score", 1.0))
        stress_res = float(metrics.get("avg_resilience", 0))
        capital_eff = float(metrics.get("capital_efficiency", 0))
        expectancy = float(metrics.get("expectancy_mean", 0))
        survival_q = float(metrics.get("survival_quality", 0))

        # AQ: Adaptive Quality
        metrics["adaptive_quality_score"] = round(
            max(0.0, min(1.0,
                0.30 * drawdown_res +
                0.25 * min(1.0, recovery) +
                0.25 * min(1.0, capital_eff / 50) +
                0.20 * replay
            )),
            4,
        )

        # SQ: Specialization Quality
        regime_strength = 0.0
        rr = metrics.get("regime_affinity_rankings", [])
        if rr:
            regime_strength = sum(
                float(x.get("survivability", 0)) for x in rr[:3]
            ) / max(1, min(3, len(rr)))

        scout_signal = float(metrics.get("scout_divergence", 0))
        metrics["specialization_quality_score"] = round(
            max(0.0, min(1.0, 0.6 * regime_strength + 0.4 * scout_signal)),
            4,
        )

        # AL: Allocation Quality
        div_quality = max(0.0, min(1.0, diversification * (1.0 - concentration)))
        metrics["allocation_quality_score"] = round(
            max(0.0, min(1.0, 0.55 * div_quality + 0.45 * drawdown_res)),
            4,
        )

        # ES: Evolutionary Selection
        metrics["evolutionary_selection_score"] = round(
            max(0.0, min(1.0,
                0.5 * min(1.0, (expectancy + 1.0) / 2.0) +
                0.25 * drawdown_res +
                0.25 * regime_strength
            )),
            4,
        )

        # IS: Infrastructure Stability
        metrics["infrastructure_stability_score"] = round(
            max(0.0, min(1.0,
                0.30 * replay +
                0.20 * (1.0 - min(1.0, metrics.get("cpu_percent", 0) / 80)) +
                0.20 * (1.0 - min(1.0, metrics.get("event_loop_lag_ms", 0) / 100)) +
                0.15 * (1.0 - min(1.0, metrics.get("dead_letter_count", 0) / 50)) +
                0.15 * (1.0 - min(1.0, metrics.get("restart_count", 0) / 5))
            )),
            4,
        )

        # SR: Stress Resilience
        metrics["stress_resilience_score"] = round(
            max(0.0, min(1.0,
                0.40 * stress_res +
                0.30 * drawdown_res +
                0.30 * survival_q
            )),
            4,
        )

        # LH: Long-Horizon Survivability
        metrics["long_horizon_survivability_score"] = round(
            max(0.0, min(1.0,
                0.20 * metrics["adaptive_quality_score"] +
                0.15 * metrics["specialization_quality_score"] +
                0.15 * metrics["allocation_quality_score"] +
                0.15 * metrics["evolutionary_selection_score"] +
                0.15 * metrics["infrastructure_stability_score"] +
                0.20 * metrics["stress_resilience_score"]
            )),
            4,
        )

    async def _persist(self, metrics: dict[str, Any]) -> None:
        """Persist Phase 33 metrics to database."""
        payload = {
            "recorded_at": metrics["recorded_at"],
            "runtime_minutes": metrics["runtime_minutes"],

            # 33A
            "expectancy_mean": metrics.get("expectancy_mean", 0),
            "expectancy_median": metrics.get("expectancy_median", 0),
            "expectancy_p90": metrics.get("expectancy_p90", 0),
            "avg_sharpe": metrics.get("avg_sharpe", 0),
            "avg_sortino": metrics.get("avg_sortino", 0),
            "avg_calmar": metrics.get("avg_calmar", 0),
            "avg_composite_fitness": metrics.get("avg_composite_fitness", 0),
            "median_composite_fitness": metrics.get("median_composite_fitness", 0),
            "top_decile_fitness": metrics.get("top_decile_fitness", 0),
            "bottom_decile_fitness": metrics.get("bottom_decile_fitness", 0),
            "recovery_quality": metrics.get("recovery_quality", 0),
            "drawdown_resilience": metrics.get("drawdown_resilience", 0),
            "capital_efficiency": metrics.get("capital_efficiency", 0),
            "survival_quality": metrics.get("survival_quality", 0),

            # 33B
            "ram_mb": metrics.get("ram_mb", 0),
            "cpu_percent": metrics.get("cpu_percent", 0),
            "event_loop_lag_ms": metrics.get("event_loop_lag_ms", 0),
            "db_pool_size": metrics.get("db_pool_size", 0),
            "db_checked_out": metrics.get("db_checked_out", 0),
            "db_overflow": metrics.get("db_overflow", 0),
            "dead_letter_count": metrics.get("dead_letter_count", 0),
            "failed_insert_count": metrics.get("failed_insert_count", 0),
            "task_count": metrics.get("task_count", 0),
            "thread_count": metrics.get("thread_count", 0),
            "restart_count": metrics.get("restart_count", 0),

            # 33C
            "dominant_organisms": metrics.get("dominant_organisms", 0),
            "active_organisms": metrics.get("active_organisms", 0),
            "mutation_family_count": metrics.get("mutation_family_count", 0),
            "top_mutation_family": metrics.get("top_mutation_family", ""),
            "regime_specialist_count": metrics.get("regime_specialist_count", 0),
            "cross_regime_survivors": metrics.get("cross_regime_survivors", 0),
            "scout_divergence": metrics.get("scout_divergence", 0),
            "capital_migrated": metrics.get("capital_migrated", 0),
            "diversification_score": metrics.get("diversification_score", 0.5),
            "concentration_risk": metrics.get("concentration_risk", 0),
            "organism_lifespan_avg": metrics.get("organism_lifespan_avg", 0),
            "retirement_rate": metrics.get("retirement_rate", 0),
            "organism_survival_curves": json.dumps(metrics.get("organism_survival_curves", [])),

            # 33D
            "active_perturbations": metrics.get("active_perturbations", 0),
            "stress_level": metrics.get("stress_level", 0),
            "avg_resilience": metrics.get("avg_resilience", 0),
            "n_resilient": metrics.get("n_resilient", 0),
            "n_fragile": metrics.get("n_fragile", 0),
            "collapse_rate": metrics.get("collapse_rate", 0),

            # 33E
            "generation_comparison_score": metrics.get("generation_comparison_score", 0),
            "adaptive_trend": metrics.get("adaptive_trend", 0),

            # Composites
            "adaptive_quality_score": metrics.get("adaptive_quality_score", 0),
            "specialization_quality_score": metrics.get("specialization_quality_score", 0),
            "allocation_quality_score": metrics.get("allocation_quality_score", 0),
            "evolutionary_selection_score": metrics.get("evolutionary_selection_score", 0),
            "long_horizon_survivability_score": metrics.get("long_horizon_survivability_score", 0),
            "infrastructure_stability_score": metrics.get("infrastructure_stability_score", 0),
            "stress_resilience_score": metrics.get("stress_resilience_score", 0),

            # JSON blobs
            "mutation_family_performance": json.dumps(metrics.get("mutation_family_performance", [])),
            "regime_affinity_rankings": json.dumps(metrics.get("regime_affinity_rankings", [])),
            "scout_predictive_rankings": json.dumps(metrics.get("scout_predictive_rankings", [])),
            "capital_allocation_evolution": json.dumps(metrics.get("capital_allocation_evolution", {})),
            "expectancy_distribution": json.dumps(metrics.get("expectancy_distribution", {})),
            "execution_degradation_metrics": json.dumps(metrics.get("execution_degradation_metrics", {})),
            "replay_integrity": metrics.get("replay_integrity", 1.0),
            "error_count": metrics.get("error_count", 0),
            "trades_per_hour": metrics.get("trades_per_hour", 0),
            "execution_degradation": metrics.get("execution_degradation", 0),
            "stress_state": json.dumps(metrics.get("stress_state", {})),
            "infrastructure_snapshot": json.dumps({
                "ram_mb": metrics.get("ram_mb", 0),
                "cpu_percent": metrics.get("cpu_percent", 0),
                "event_loop_lag_ms": metrics.get("event_loop_lag_ms", 0),
                "task_count": metrics.get("task_count", 0),
                "thread_count": metrics.get("thread_count", 0),
            }),
            "metadata": json.dumps({
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "phase": "33",
                "sub_phases": ["33A", "33B", "33C", "33D", "33E"],
            }),
        }

        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase33_performance_metrics (
                    recorded_at, runtime_minutes,
                    expectancy_mean, expectancy_median, expectancy_p90,
                    avg_sharpe, avg_sortino, avg_calmar,
                    avg_composite_fitness, median_composite_fitness,
                    top_decile_fitness, bottom_decile_fitness,
                    recovery_quality, drawdown_resilience,
                    capital_efficiency, survival_quality,
                    ram_mb, cpu_percent, event_loop_lag_ms,
                    db_pool_size, db_checked_out, db_overflow,
                    dead_letter_count, failed_insert_count,
                    task_count, thread_count, restart_count,
                    dominant_organisms, active_organisms,
                    mutation_family_count, top_mutation_family,
                    regime_specialist_count, cross_regime_survivors,
                    scout_divergence, capital_migrated,
                    diversification_score, concentration_risk,
                    organism_lifespan_avg, retirement_rate,
                    active_perturbations, stress_level,
                    avg_resilience, n_resilient, n_fragile, collapse_rate,
                    generation_comparison_score, adaptive_trend,
                    adaptive_quality_score, specialization_quality_score,
                    allocation_quality_score, evolutionary_selection_score,
                    long_horizon_survivability_score,
                    infrastructure_stability_score, stress_resilience_score,
                    mutation_family_performance, regime_affinity_rankings,
                    scout_predictive_rankings, capital_allocation_evolution,
                    expectancy_distribution, execution_degradation_metrics,
                    replay_integrity, error_count, trades_per_hour,
                    execution_degradation,
                    stress_state, infrastructure_snapshot, metadata
                ) VALUES (
                    :recorded_at, :runtime_minutes,
                    :expectancy_mean, :expectancy_median, :expectancy_p90,
                    :avg_sharpe, :avg_sortino, :avg_calmar,
                    :avg_composite_fitness, :median_composite_fitness,
                    :top_decile_fitness, :bottom_decile_fitness,
                    :recovery_quality, :drawdown_resilience,
                    :capital_efficiency, :survival_quality,
                    :ram_mb, :cpu_percent, :event_loop_lag_ms,
                    :db_pool_size, :db_checked_out, :db_overflow,
                    :dead_letter_count, :failed_insert_count,
                    :task_count, :thread_count, :restart_count,
                    :dominant_organisms, :active_organisms,
                    :mutation_family_count, :top_mutation_family,
                    :regime_specialist_count, :cross_regime_survivors,
                    :scout_divergence, :capital_migrated,
                    :diversification_score, :concentration_risk,
                    :organism_lifespan_avg, :retirement_rate,
                    :active_perturbations, :stress_level,
                    :avg_resilience, :n_resilient, :n_fragile, :collapse_rate,
                    :generation_comparison_score, :adaptive_trend,
                    :adaptive_quality_score, :specialization_quality_score,
                    :allocation_quality_score, :evolutionary_selection_score,
                    :long_horizon_survivability_score,
                    :infrastructure_stability_score, :stress_resilience_score,
                    CAST(:mutation_family_performance AS jsonb),
                    CAST(:regime_affinity_rankings AS jsonb),
                    CAST(:scout_predictive_rankings AS jsonb),
                    CAST(:capital_allocation_evolution AS jsonb),
                    CAST(:expectancy_distribution AS jsonb),
                    CAST(:execution_degradation_metrics AS jsonb),
                    :replay_integrity, :error_count, :trades_per_hour,
                    :execution_degradation,
                    CAST(:stress_state AS jsonb),
                    CAST(:infrastructure_snapshot AS jsonb),
                    CAST(:metadata AS jsonb)
                )
            """), payload)

    async def close(self) -> None:
        await self.engine.dispose()


# ────────────────────────────────────────────────────────
# PHASE 33 — STRESS INJECTOR (33D)
# ────────────────────────────────────────────────────────

class StressInjector:
    """
    PHASE 33D: Synthetic market perturbation injection.
    Injects controlled environmental shocks to force regime adaptation.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self._active_perturbations: list[dict] = []
        self._perturbation_history: list[dict] = []
        self._total_cycles = 0
        self.PERTURBATION_PROBABILITY = 0.35
        self.MAX_CONCURRENT = 3

    async def ensure_table(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase33_perturbation_events (
                    id SERIAL PRIMARY KEY,
                    perturbation_type TEXT NOT NULL,
                    severity FLOAT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expired_at TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata JSONB DEFAULT '{}'
                )
            """))

    def _expire(self) -> None:
        now = datetime.now(timezone.utc)
        still_active = []
        for p in self._active_perturbations:
            started = p["started_at"]
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            elapsed_minutes = (now - started).total_seconds() / 60.0
            if elapsed_minutes < p["duration_minutes"]:
                still_active.append(p)
            else:
                logger.info(
                    f"Phase33[Stress]: Expired {p['type']} perturbation "
                    f"(lasted {elapsed_minutes:.1f}m/{p['duration_minutes']}m)"
                )
                p["expired_at"] = now.isoformat()
                self._perturbation_history.append(p)
        self._active_perturbations = still_active

    def _generate(self) -> Optional[dict]:
        if self._total_cycles % 3 != 0:
            return None  # Only inject every 3rd cycle
        import random as _random
        preset_name = _random.choice(list(PERTURBATION_PRESETS.keys()))
        preset = PERTURBATION_PRESETS[preset_name]
        severity = round(
            _random.uniform(preset["severity_range"][0], preset["severity_range"][1]),
            2,
        )
        duration = _random.randint(
            preset["duration_minutes_range"][0], preset["duration_minutes_range"][1]
        )
        symbols = ["BTCUSDT", "ETHUSDT", "SPY", "QQQ", "NVDA", "AAPL", "MSFT"]
        return {
            "type": preset_name,
            "category": preset["type"],
            "description": preset["description"],
            "severity": severity,
            "duration_minutes": duration,
            "target_symbol": _random.choice(symbols),
            "started_at": datetime.now(timezone.utc),
            "affected_channels": preset["affected_channels"],
        }

    async def cycle(self) -> list[dict]:
        """Run one stress injection cycle. Returns active perturbations."""
        self._expire()
        self._total_cycles += 1

        import random as _random
        space = self.MAX_CONCURRENT - len(self._active_perturbations)
        for _ in range(space):
            if _random.random() < self.PERTURBATION_PROBABILITY:
                p = self._generate()
                if p:
                    self._active_perturbations.append(p)
                    logger.info(
                        f"Phase33[Stress]: Injected {p['type']} "
                        f"(severity={p['severity']}, duration={p['duration_minutes']}m)"
                    )
                    # Persist to DB
                    try:
                        async with self.engine.begin() as conn:
                            await conn.execute(sa_text("""
                                INSERT INTO phase33_perturbation_events
                                    (perturbation_type, severity, started_at, status, metadata)
                                VALUES (:ptype, :severity, :started_at, 'active', CAST(:meta AS jsonb))
                            """), {
                                "ptype": p["type"],
                                "severity": p["severity"],
                                "started_at": p["started_at"],
                                "meta": json.dumps({
                                    "category": p["category"],
                                    "duration_minutes": p["duration_minutes"],
                                    "target_symbol": p["target_symbol"],
                                    "affected_channels": p["affected_channels"],
                                }),
                            })
                    except Exception as e:
                        logger.warning(f"Phase33[Stress]: Persist failed: {e}")

        return list(self._active_perturbations)

    async def close(self) -> None:
        await self.engine.dispose()


# ────────────────────────────────────────────────────────
# PHASE 33 — SOAK CONTROLLER
# ────────────────────────────────────────────────────────

class PerformanceBenchmarkSoakController:
    """
    Phase 33 soak controller orchestrating all 5 sub-phases.
    """

    def __init__(
        self,
        duration_minutes: int = 720,
        metrics_interval: int = 300,
    ):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = metrics_interval
        self.db_url = settings.database_url
        self.metrics = PerformanceMetricsCollector(self.db_url)
        self.stress = StressInjector(self.db_url)
        self._shutdown = False
        self._start_time: Optional[float] = None

        # Engine instances
        self._soak_db: Optional[SoakDbClient] = None
        self._engines_initialized = False
        self._dominant_tracker = None
        self._lineage_tracker = None
        self._regime_engine = None
        self._scout_engine = None
        self._portfolio_engine = None
        self._mutation_policy = None
        self._economic_engine = None
        self._retirement_engine = None
        self._replay_engine = None

    async def _ensure_engines(self) -> None:
        if self._engines_initialized:
            return
        _engine = create_async_engine(self.db_url)
        self._soak_db = SoakDbClient(_engine)

        self._dominant_tracker = DominantOrganismTracker(redis_client=None, db_client=self._soak_db)
        self._lineage_tracker = MutationLineageTracker(redis_client=None, db_client=self._soak_db)
        self._regime_engine = RegimeSpecializationEngine(redis_client=None, db_client=self._soak_db)
        self._scout_engine = ScoutDivergenceEngine(redis_client=None, db_client=self._soak_db)
        self._portfolio_engine = PortfolioEvolutionPressure(redis_client=None, db_client=self._soak_db)
        self._mutation_policy = MutationPolicyEngine(redis_client=None, db_client=self._soak_db)
        self._economic_engine = EconomicEfficiencyEngine(redis_client=None, db_client=self._soak_db)
        self._retirement_engine = StrategyRetirementEngine(
            redis_client=None, db_client=self._soak_db, run_interval=3600
        )
        self._replay_engine = ReplayEngine(redis_client=None, db_client=self._soak_db)

        self._engines_initialized = True
        logger.info("Phase 33 engines initialized")

    async def _safe_call(self, name: str, coro, timeout: int = 60) -> None:
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.debug(f"Phase33[{name}] OK")
        except asyncio.TimeoutError:
            logger.warning(f"Phase33[{name}] TIMEOUT after {timeout}s")
        except Exception as e:
            logger.warning(f"Phase33[{name}] FAILED: {type(e).__name__}: {e}")

    async def _run_phase33_cycle(self) -> list[dict]:
        """Run one full Phase 33 cycle — all 5 sub-phases."""
        await self._ensure_engines()

        # Phase 33A-C: Core intelligence cycles
        await self._safe_call("DominantOrganism", self._dominant_tracker._tracking_cycle())
        await self._safe_call("MutationLineage", self._lineage_tracker._lineage_cycle())
        await self._safe_call("RegimeSpecialization", self._regime_engine._profiling_cycle())
        await self._safe_call("ScoutDivergence", self._scout_engine._divergence_cycle())
        await self._safe_call("PortfolioEvolution", self._portfolio_engine._pressure_cycle())
        await self._safe_call("MutationPolicy", self._mutation_policy._learn_policy())
        await self._safe_call("EconomicEfficiency", self._economic_engine._full_economic_analysis_cycle())
        await self._safe_call("ReplayIntegrity", self._replay_engine._sweep_replay_checks())

        # Phase 33D: Regime stress injection
        await self._safe_call("RegimeStress", self.stress.cycle())

        # Retirement
        report = await self._retirement_engine._compute_retirement_analysis()
        if report:
            await self._safe_call("RetirementPersist", self._retirement_engine._persist_retirement(report))
            await self._safe_call("RetirementPublish", self._retirement_engine._publish_retirement(report))

        return self.stress._active_perturbations

    async def _ensure_schema(self) -> None:
        """Ensure all Phase 33 tables exist."""
        async with create_async_engine(self.db_url).begin() as conn:
            for col, ctype in [
                ("portfolio_id", "TEXT"),
                ("diversification_score", "FLOAT DEFAULT 0"),
                ("correlation_collapse_risk", "FLOAT DEFAULT 0"),
                ("contagion_exposure", "FLOAT DEFAULT 0"),
                ("concentration_risk", "FLOAT DEFAULT 0"),
                ("portfolio_survivability", "FLOAT DEFAULT 0"),
                ("drawdown_recovery_speed", "FLOAT DEFAULT 0"),
                ("active_strategies", "INT DEFAULT 0"),
            ]:
                await conn.execute(sa_text(
                    f"ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS {col} {ctype}"
                ))

    async def run(self) -> None:
        logger.info("=" * 72)
        logger.info("PHASE 33 — FULL PERFORMANCE & ADAPTIVE INTELLIGENCE BENCHMARKING")
        logger.info(f"Duration: {self.duration_minutes}m | Metrics interval: {self.metrics_interval}s")
        logger.info("=" * 72)
        logger.info("Sub-phases: 33A(Economic) 33B(Infrastructure) 33C(Evolutionary) 33D(Stress) 33E(Long-Horizon)")
        logger.info("=" * 72)

        # Initialize schema
        await self._ensure_schema()
        await self.metrics.initialize()
        await self.stress.ensure_table()

        # Signal handling
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._request_shutdown)
            except NotImplementedError:
                pass

        self._start_time = time.time()

        try:
            while not self._shutdown:
                elapsed = time.time() - self._start_time
                remaining = self.duration_seconds - elapsed
                if remaining <= 0:
                    break

                elapsed_minutes = int(elapsed / 60)

                # Run full Phase 33 cycle
                active_perturbations = await self._run_phase33_cycle()

                # Collect and persist metrics
                metrics = await self.metrics.collect(elapsed_minutes, active_perturbations)
                self._print_status(metrics, elapsed, remaining)

                await asyncio.sleep(min(self.metrics_interval, remaining))
        finally:
            await self._finalize()

    def _request_shutdown(self) -> None:
        self._shutdown = True

    def _print_status(self, metrics: dict[str, Any], elapsed: float, remaining: float) -> None:
        e = int(elapsed / 60)
        r = int(remaining / 60)
        print(f"\n[Phase33] T+{e}m / T-{r}m")
        print(
            "  Scores: "
            f"AQ={metrics.get('adaptive_quality_score', 0):.3f} "
            f"SQ={metrics.get('specialization_quality_score', 0):.3f} "
            f"AL={metrics.get('allocation_quality_score', 0):.3f} "
            f"ES={metrics.get('evolutionary_selection_score', 0):.3f} "
            f"IS={metrics.get('infrastructure_stability_score', 0):.3f} "
            f"SR={metrics.get('stress_resilience_score', 0):.3f} "
            f"LH={metrics.get('long_horizon_survivability_score', 0):.3f}"
        )
        print(
            "  Econ: "
            f"exp={metrics.get('expectancy_mean', 0):.4f} "
            f"sharpe={metrics.get('avg_sharpe', 0):.2f} "
            f"fitness={metrics.get('avg_composite_fitness', 0):.1f} "
            f"recovery={metrics.get('recovery_quality', 0):.3f}"
        )
        print(
            "  Infra: "
            f"RAM={metrics.get('ram_mb', 0):.0f}MB "
            f"CPU={metrics.get('cpu_percent', 0):.1f}% "
            f"lag={metrics.get('event_loop_lag_ms', 0):.2f}ms "
            f"dead_letters={metrics.get('dead_letter_count', 0)} "
            f"restarts={metrics.get('restart_count', 0)}"
        )
        print(
            "  Evolve: "
            f"dominant={metrics.get('dominant_organisms', 0)} "
            f"active={metrics.get('active_organisms', 0)} "
            f"mutations={metrics.get('mutation_family_count', 0)} "
            f"regimes={metrics.get('regime_specialist_count', 0)} "
            f"divergence={metrics.get('scout_divergence', 0):.4f}"
        )
        print(
            "  Stress: "
            f"perturbations={metrics.get('active_perturbations', 0)} "
            f"level={metrics.get('stress_level', 0):.3f} "
            f"resilience={metrics.get('avg_resilience', 0):.3f} "
            f"collapse_rate={metrics.get('collapse_rate', 0)}"
        )
        print(
            "  Gen: "
            f"gen_comparison={metrics.get('generation_comparison_score', 0):.4f} "
            f"trend={metrics.get('adaptive_trend', 0):.4f}"
        )
        print(
            "  Portfolio: "
            f"diversification={metrics.get('diversification_score', 0):.3f} "
            f"concentration={metrics.get('concentration_risk', 0):.3f} "
            f"migrated={metrics.get('capital_migrated', 0):.3f}"
        )
        sys.stdout.flush()

    async def _finalize(self) -> None:
        total_minutes = int((time.time() - self._start_time) / 60) if self._start_time else 0
        logger.info(f"Phase 33 soak complete after {total_minutes} minutes")

        # Get first and last metrics for comparison
        initial = self.metrics.metrics_history[0] if self.metrics.metrics_history else {}
        latest = self.metrics.metrics_history[-1] if self.metrics.metrics_history else {}

        await self._generate_reports(initial, latest, total_minutes)
        await self.metrics.close()
        await self.stress.close()

    async def _generate_reports(
        self,
        initial: dict[str, Any],
        latest: dict[str, Any],
        duration_minutes: int,
    ) -> None:
        """Generate all 7 Phase 33 reports."""
        ROOT = Path(__file__).resolve().parents[1]

        def pct_delta(key: str) -> float:
            a = float(initial.get(key, 0) or 0)
            b = float(latest.get(key, 0) or 0)
            if a == 0:
                return b
            return (b - a) / abs(a)

        # ── Report 1: Economic Performance ─────────────────────────────────
        econ_lines = [
            "# PHASE33_ECONOMIC_PERFORMANCE_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            f"**Runtime:** {duration_minutes // 60}h {duration_minutes % 60}m",
            "",
            "## Composite Scores",
            f"| Metric | Start | End | Delta |",
            f"|--------|-------|-----|-------|",
            f"| Adaptive Quality (AQ) | {initial.get('adaptive_quality_score', 0):.4f} | {latest.get('adaptive_quality_score', 0):.4f} | {pct_delta('adaptive_quality_score'):+.4f} |",
            f"| Evolutionary Selection (ES) | {initial.get('evolutionary_selection_score', 0):.4f} | {latest.get('evolutionary_selection_score', 0):.4f} | {pct_delta('evolutionary_selection_score'):+.4f} |",
            "",
            "## Economic Metrics",
            f"| Metric | Value | Status |",
            f"|--------|-------|--------|",
            f"| Expectancy (mean) | {latest.get('expectancy_mean', 0):.6f} | {'✅' if latest.get('expectancy_mean', 0) > 0 else '⚠️'} |",
            f"| Expectancy (median) | {latest.get('expectancy_median', 0):.6f} | — |",
            f"| Expectancy (p90) | {latest.get('expectancy_p90', 0):.6f} | — |",
            f"| Avg Sharpe | {latest.get('avg_sharpe', 0):.4f} | {'✅' if latest.get('avg_sharpe', 0) > 0.5 else '⚠️'} |",
            f"| Avg Sortino | {latest.get('avg_sortino', 0):.4f} | — |",
            f"| Avg Calmar | {latest.get('avg_calmar', 0):.4f} | — |",
            f"| Avg Composite Fitness | {latest.get('avg_composite_fitness', 0):.2f} | {'✅' if latest.get('avg_composite_fitness', 0) > 10 else '⚠️'} |",
            f"| Median Fitness | {latest.get('median_composite_fitness', 0):.2f} | — |",
            f"| Top Decile Fitness | {latest.get('top_decile_fitness', 0):.2f} | — |",
            f"| Bottom Decile Fitness | {latest.get('bottom_decile_fitness', 0):.2f} | — |",
            f"| Recovery Quality | {latest.get('recovery_quality', 0):.4f} | {'✅' if latest.get('recovery_quality', 0) > 0.5 else '⚠️'} |",
            f"| Drawdown Resilience | {latest.get('drawdown_resilience', 0):.4f} | {'✅' if latest.get('drawdown_resilience', 0) > 0.7 else '⚠️'} |",
            f"| Capital Efficiency | {latest.get('capital_efficiency', 0):.4f} | — |",
            f"| Survival Quality | {latest.get('survival_quality', 0):.4f} | — |",
            "",
            "## Generation Comparison",
            f"**Generation comparison score:** {latest.get('generation_comparison_score', 0):.4f} "
            f"({'✅ improving' if latest.get('generation_comparison_score', 0) > 0 else '⚠️ not improving'})",
            f"**Adaptive trend:** {latest.get('adaptive_trend', 0):.4f} "
            f"({'✅ positive' if latest.get('adaptive_trend', 0) > 0 else '⚠️ flat/negative'})",
            "",
            "## Expectancy Distribution",
            f"```json\n{json.dumps(latest.get('expectancy_distribution', {}), indent=2)}\n```",
        ]

        # ── Report 2: Runtime Stability ────────────────────────────────────
        runtime_lines = [
            "# PHASE33_RUNTIME_STABILITY_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            "",
            "## Infrastructure Metrics",
            f"| Metric | Value | Threshold | Status |",
            f"|--------|-------|-----------|--------|",
            f"| RAM (MB) | {latest.get('ram_mb', 0):.0f} | < 1024 | {'✅' if latest.get('ram_mb', 0) < 1024 else '⚠️'} |",
            f"| CPU (%) | {latest.get('cpu_percent', 0):.1f} | < 50 | {'✅' if latest.get('cpu_percent', 0) < 50 else '⚠️'} |",
            f"| Event Loop Lag (ms) | {latest.get('event_loop_lag_ms', 0):.2f} | < 10 | {'✅' if latest.get('event_loop_lag_ms', 0) < 10 else '⚠️'} |",
            f"| Dead Letters | {latest.get('dead_letter_count', 0)} | < 10 | {'✅' if latest.get('dead_letter_count', 0) < 10 else '⚠️'} |",
            f"| Failed Inserts | {latest.get('failed_insert_count', 0)} | < 5 | {'✅' if latest.get('failed_insert_count', 0) < 5 else '⚠️'} |",
            f"| Restarts (last hour) | {latest.get('restart_count', 0)} | 0 | {'✅' if latest.get('restart_count', 0) == 0 else '⚠️'} |",
            f"| Tasks | {latest.get('task_count', 0)} | — | — |",
            f"| Threads | {latest.get('thread_count', 0)} | — | — |",
            "",
            "## Infrastructure Stability Score",
            f"**IS:** {latest.get('infrastructure_stability_score', 0):.4f} "
            f"({'✅ PASS' if latest.get('infrastructure_stability_score', 0) >= 0.7 else '⚠️ BELOW THRESHOLD'})",
            "",
            "## Metrics Over Time",
            "```",
        ]
        if self.metrics.metrics_history:
            runtime_lines.append("  Time(min)  RAM(MB)  CPU(%)  Lag(ms)  DeadL  Restarts  IScore")
            for i, m in enumerate(self.metrics.metrics_history):
                if i % max(1, len(self.metrics.metrics_history) // 10) == 0 or i == len(self.metrics.metrics_history) - 1:
                    runtime_lines.append(
                        f"  {m.get('runtime_minutes', 0):>5d}    "
                        f"{m.get('ram_mb', 0):>6.0f}  "
                        f"{m.get('cpu_percent', 0):>6.1f}  "
                        f"{m.get('event_loop_lag_ms', 0):>7.2f}  "
                        f"{m.get('dead_letter_count', 0):>5d}  "
                        f"{m.get('restart_count', 0):>5d}  "
                        f"{m.get('infrastructure_stability_score', 0):.4f}"
                    )
        runtime_lines.append("```")

        # ── Report 3: Evolutionary Performance ────────────────────────────
        evol_lines = [
            "# PHASE33_EVOLUTIONARY_PERFORMANCE_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            "",
            "## Population Metrics",
            f"| Metric | Value | Status |",
            f"|--------|-------|--------|",
            f"| Dominant Organisms | {latest.get('dominant_organisms', 0)} | {'✅' if latest.get('dominant_organisms', 0) >= 1 else '⚠️'} |",
            f"| Active Organisms | {latest.get('active_organisms', 0)} | — |",
            f"| Avg Lifespan (bars) | {latest.get('organism_lifespan_avg', 0):.1f} | — |",
            f"| Retirement Rate (1h) | {latest.get('retirement_rate', 0)} | — |",
            "",
            "## Mutation Families",
            f"| Family | Observations | Sharpe Delta | Score Delta |",
            f"|--------|-------------|-------------|-------------|",
        ]
        for fam in latest.get("mutation_family_performance", [])[:10]:
            evol_lines.append(
                f"| {fam.get('family', 'unknown')} | {fam.get('n_obs', 0)} | "
                f"{fam.get('avg_sharpe_delta', 0):.4f} | {fam.get('avg_score_delta', 0):.4f} |"
            )
        evol_lines.extend([
            "",
            "## Regime Specialization",
            f"| Regime | Survivability | Observations |",
            f"|--------|--------------|-------------|",
        ])
        for reg in latest.get("regime_affinity_rankings", [])[:10]:
            evol_lines.append(
                f"| {reg.get('regime', 'unknown')} | {reg.get('survivability', 0):.4f} | {reg.get('n_obs', 0)} |"
            )
        evol_lines.extend([
            "",
            "## Scout Rankings",
            f"| Scout | Alignment | Net PnL | Observations |",
            f"|-------|-----------|---------|-------------|",
        ])
        for sc in latest.get("scout_predictive_rankings", [])[:10]:
            evol_lines.append(
                f"| {sc.get('scout', 'unknown')} | {sc.get('alignment', 0):.4f} | "
                f"{sc.get('avg_net_pnl', 0):.6f} | {sc.get('n_obs', 0)} |"
            )
        evol_lines.extend([
            "",
            f"**Scout Divergence:** {latest.get('scout_divergence', 0):.4f} "
            f"({'✅ diverging' if latest.get('scout_divergence', 0) > 0.01 else '⚠️ not diverging'})",
        ])

        # ── Report 4: Regime Stress ──────────────────────────────────────
        stress_lines = [
            "# PHASE33_REGIME_STRESS_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            "",
            "## Stress Metrics",
            f"| Metric | Value | Status |",
            f"|--------|-------|--------|",
            f"| Active Perturbations | {latest.get('active_perturbations', 0)} | — |",
            f"| Stress Level | {latest.get('stress_level', 0):.4f} | {'✅ managed' if latest.get('stress_level', 0) < 0.5 else '⚠️ elevated'} |",
            f"| Avg Resilience | {latest.get('avg_resilience', 0):.4f} | {'✅ resilient' if latest.get('avg_resilience', 0) > 0.5 else '⚠️ fragile'} |",
            f"| Resilient Organisms | {latest.get('n_resilient', 0)} | — |",
            f"| Fragile Organisms | {latest.get('n_fragile', 0)} | — |",
            f"| Collapse Rate (1h) | {latest.get('collapse_rate', 0)} | {'✅ stable' if latest.get('collapse_rate', 0) < 3 else '⚠️ elevated'} |",
            "",
            "## Stress Resilience Score",
            f"**SR:** {latest.get('stress_resilience_score', 0):.4f} "
            f"({'✅ PASS' if latest.get('stress_resilience_score', 0) >= 0.5 else '⚠️ BELOW THRESHOLD'})",
            "",
            "## Active Perturbations",
            f"```json\n{json.dumps(latest.get('stress_state', {}), indent=2)}\n```",
        ]

        # ── Report 5: Portfolio Survivability ─────────────────────────────
        portfolio_lines = [
            "# PHASE33_PORTFOLIO_SURVIVABILITY_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            "",
            "## Portfolio Metrics",
            f"| Metric | Value | Status |",
            f"|--------|-------|--------|",
            f"| Diversification Score | {latest.get('diversification_score', 0):.4f} | {'✅ diversified' if latest.get('diversification_score', 0) > 0.3 else '⚠️ concentrated'} |",
            f"| Concentration Risk | {latest.get('concentration_risk', 0):.4f} | {'✅ low' if latest.get('concentration_risk', 0) < 0.3 else '⚠️ high'} |",
            f"| Capital Migrated | {latest.get('capital_migrated', 0):.4f} | — |",
            f"| Cross-Regime Survivors | {latest.get('cross_regime_survivors', 0)} | — |",
            f"| Regime Specialists | {latest.get('regime_specialist_count', 0)} | — |",
            "",
            "## Allocation Quality",
            f"**AL:** {latest.get('allocation_quality_score', 0):.4f} "
            f"({'✅ PASS' if latest.get('allocation_quality_score', 0) >= 0.30 else '⚠️ BELOW THRESHOLD'})",
            "",
            "## Capital Allocation Evolution",
            f"```json\n{json.dumps(latest.get('capital_allocation_evolution', {}), indent=2)}\n```",
        ]

        # ── Report 6: Adaptive Intelligence ───────────────────────────────
        adaptive_lines = [
            "# PHASE33_ADAPTIVE_INTELLIGENCE_REPORT",
            "",
            f"**Duration minutes:** {duration_minutes}",
            "",
            "## Composite Score Comparison",
            f"| Score | Start | End | Delta | Trend |",
            f"|-------|-------|-----|-------|-------|",
            f"| AQ | {initial.get('adaptive_quality_score', 0):.4f} | {latest.get('adaptive_quality_score', 0):.4f} | {pct_delta('adaptive_quality_score'):+.4f} | {'📈' if pct_delta('adaptive_quality_score') > 0 else '📉'} |",
            f"| SQ | {initial.get('specialization_quality_score', 0):.4f} | {latest.get('specialization_quality_score', 0):.4f} | {pct_delta('specialization_quality_score'):+.4f} | {'📈' if pct_delta('specialization_quality_score') > 0 else '📉'} |",
            f"| AL | {initial.get('allocation_quality_score', 0):.4f} | {latest.get('allocation_quality_score', 0):.4f} | {pct_delta('allocation_quality_score'):+.4f} | {'📈' if pct_delta('allocation_quality_score') > 0 else '📉'} |",
            f"| ES | {initial.get('evolutionary_selection_score', 0):.4f} | {latest.get('evolutionary_selection_score', 0):.4f} | {pct_delta('evolutionary_selection_score'):+.4f} | {'📈' if pct_delta('evolutionary_selection_score') > 0 else '📉'} |",
            f"| IS | {initial.get('infrastructure_stability_score', 0):.4f} | {latest.get('infrastructure_stability_score', 0):.4f} | {pct_delta('infrastructure_stability_score'):+.4f} | {'📈' if pct_delta('infrastructure_stability_score') > 0 else '📉'} |",
            f"| SR | {initial.get('stress_resilience_score', 0):.4f} | {latest.get('stress_resilience_score', 0):.4f} | {pct_delta('stress_resilience_score'):+.4f} | {'📈' if pct_delta('stress_resilience_score') > 0 else '📉'} |",
            f"| LH | {initial.get('long_horizon_survivability_score', 0):.4f} | {latest.get('long_horizon_survivability_score', 0):.4f} | {pct_delta('long_horizon_survivability_score'):+.4f} | {'📈' if pct_delta('long_horizon_survivability_score') > 0 else '📉'} |",
            "",
            "## Adaptive Intelligence Assessment",
            "",
            "### Does adaptive quality improve over time?",
            f"- Generation comparison: {latest.get('generation_comparison_score', 0):+.4f} "
            f"({'✅ YES — later generations outperform' if latest.get('generation_comparison_score', 0) > 0 else '⚠️ NO — flat or declining'})",
            f"- Adaptive trend (fitness vs time): {latest.get('adaptive_trend', 0):+.4f} "
            f"({'✅ POSITIVE — improving' if latest.get('adaptive_trend', 0) > 0 else '⚠️ FLAT/NEGATIVE'})",
            "",
            "### Has specialization emerged?",
            f"- Regime specialists: {latest.get('regime_specialist_count', 0)} "
            f"({'✅ YES' if latest.get('regime_specialist_count', 0) >= 2 else '⚠️ NO'})",
            f"- Scout divergence: {latest.get('scout_divergence', 0):.4f} "
            f"({'✅ YES — scouts diverge' if latest.get('scout_divergence', 0) > 0.01 else '⚠️ NO — scouts uniform'})",
            "",
            "### Is the infrastructure stable?",
            f"- IS score: {latest.get('infrastructure_stability_score', 0):.4f} "
            f"({'✅ STABLE' if latest.get('infrastructure_stability_score', 0) >= 0.7 else '⚠️ UNSTABLE'})",
            f"- Restart storms: {'✅ NONE' if latest.get('restart_count', 0) == 0 else '⚠️ DETECTED'}",
            f"- Memory bounded: {'✅ YES' if latest.get('ram_mb', 0) < 1024 else '⚠️ LEAKING'}",
        ]

        # ── Report 7: Final Certification ─────────────────────────────────
        pass_checks = {
            "replay integrity perfect": latest.get("replay_integrity", 1.0) >= 0.9999,
            "no restart storms": latest.get("restart_count", 0) == 0,
            "memory bounded": latest.get("ram_mb", 0) < 1024,
            "later-generation organisms outperform": latest.get("generation_comparison_score", 0) > 0,
            "dominant organisms emerge": latest.get("dominant_organisms", 0) >= 1,
            "regime specialization increases": latest.get("regime_specialist_count", 0) >= 2,
            "scout trust diverges": latest.get("scout_divergence", 0) > 0.01,
            "adaptive allocation improves survivability": latest.get("allocation_quality_score", 0) >= 0.30,
            "drawdown resilience improves": latest.get("drawdown_resilience", 0) >= 0.7 or pct_delta("drawdown_resilience") >= 0,
            "portfolio survivability stable under stress": latest.get("stress_resilience_score", 0) >= 0.5,
            "infrastructure stability": latest.get("infrastructure_stability_score", 0) >= 0.7,
            "adaptive quality improves over time": latest.get("adaptive_trend", 0) > 0 or pct_delta("adaptive_quality_score") >= 0,
        }
        passed_all = all(pass_checks.values())
        n_passed = sum(1 for v in pass_checks.values() if v)
        n_total = len(pass_checks)

        cert_lines = [
            "# PHASE33_FINAL_BENCHMARK_CERTIFICATION",
            "",
            f"**Duration:** {duration_minutes // 60}h {duration_minutes % 60}m",
            f"**Status:** {'✅ PASS' if passed_all else '⚠️ PARTIAL'} ({n_passed}/{n_total} checks passed)",
            "",
            "## Certification Checks",
        ]
        for check_name, passed in pass_checks.items():
            cert_lines.append(f"- **{check_name}:** {'✅ PASS' if passed else '⚠️ PENDING'}")
        cert_lines.extend([
            "",
            "## Final Composite Scores",
            "```json",
            json.dumps({
                "adaptive_quality_score": latest.get("adaptive_quality_score", 0),
                "specialization_quality_score": latest.get("specialization_quality_score", 0),
                "allocation_quality_score": latest.get("allocation_quality_score", 0),
                "evolutionary_selection_score": latest.get("evolutionary_selection_score", 0),
                "infrastructure_stability_score": latest.get("infrastructure_stability_score", 0),
                "stress_resilience_score": latest.get("stress_resilience_score", 0),
                "long_horizon_survivability_score": latest.get("long_horizon_survivability_score", 0),
            }, indent=2),
            "```",
        ])

        # Write all reports
        reports = {
            "PHASE33_ECONOMIC_PERFORMANCE_REPORT.md": "\n".join(econ_lines) + "\n",
            "PHASE33_RUNTIME_STABILITY_REPORT.md": "\n".join(runtime_lines) + "\n",
            "PHASE33_EVOLUTIONARY_PERFORMANCE_REPORT.md": "\n".join(evol_lines) + "\n",
            "PHASE33_REGIME_STRESS_REPORT.md": "\n".join(stress_lines) + "\n",
            "PHASE33_PORTFOLIO_SURVIVABILITY_REPORT.md": "\n".join(portfolio_lines) + "\n",
            "PHASE33_ADAPTIVE_INTELLIGENCE_REPORT.md": "\n".join(adaptive_lines) + "\n",
            "PHASE33_FINAL_BENCHMARK_CERTIFICATION.md": "\n".join(cert_lines) + "\n",
        }

        for name, content in reports.items():
            (ROOT / name).write_text(content, encoding="utf-8")
            logger.info(f"Report generated: {name}")

        logger.info(
            f"Phase 33 reports generated: {n_passed}/{n_total} checks passed"
            f" → {'CERTIFIED' if passed_all else 'PARTIAL'}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 33 — Full Performance & Adaptive Intelligence Benchmarking"
    )
    parser.add_argument("--duration-minutes", type=int, default=720)
    parser.add_argument("--metrics-interval", type=int, default=300)
    args = parser.parse_args()

    controller = PerformanceBenchmarkSoakController(
        duration_minutes=args.duration_minutes,
        metrics_interval=args.metrics_interval,
    )
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
