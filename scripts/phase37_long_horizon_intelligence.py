"""
phase37_long_horizon_intelligence.py - Phase 37 Long-Horizon Adaptive Intelligence Evolution.

Usage:
    python scripts/phase37_long_horizon_intelligence.py --duration-minutes 720
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
import inspect
import uuid
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas.agents.l6_portfolio.portfolio_evolution_pressure import PortfolioEvolutionPressure
from atlas.agents.l7_meta.copy_analytics_engine import CopyAnalyticsEngine
from atlas.agents.l7_meta.dominant_organism_tracker import DominantOrganismTracker
from atlas.agents.l7_meta.drift_detection_engine import DriftDetectionEngine
from atlas.agents.l7_meta.economic_attribution_engine import EconomicAttributionEngine
from atlas.agents.l7_meta.economic_efficiency_engine import EconomicEfficiencyEngine
from atlas.agents.l7_meta.feature_evolution_engine import FeatureEvolutionEngine
from atlas.agents.l7_meta.failure_analysis_engine import FailureAnalysisEngine
from atlas.agents.l7_meta.hypothesis_engine import HypothesisEngine
from atlas.agents.l7_meta.mutation_lineage_tracker import MutationLineageTracker
from atlas.agents.l7_meta.mutation_policy_engine import MutationPolicyEngine
from atlas.agents.l7_meta.regime_specialization_engine import RegimeSpecializationEngine
from atlas.agents.l7_meta.regime_stress_engine import RegimeStressEngine
from atlas.agents.l7_meta.replay_engine import ReplayEngine
from atlas.agents.l7_meta.scout_divergence_engine import ScoutDivergenceEngine
from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine
from atlas.agents.l7_meta.strategy_retirement_engine import StrategyRetirementEngine
from atlas.config.settings import settings
from atlas.core.persistence_integrity import normalize_uuid_params
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.governance.context import GovernanceExecutionContext


class SoakDbClient:
    def __init__(self, engine):
        self.engine = engine

    async def _execute_insert(self, query: str, params: dict) -> None:
        from sqlalchemy import text as _t
        from atlas.data.storage.timescale_client import _extract_table_name_from_insert

        table_name = _extract_table_name_from_insert(query)
        normalized, recovered = normalize_uuid_params(
            params,
            table_name=table_name,
            context="Phase37SoakDbClient._execute_insert",
        )
        if recovered:
            logger.warning(
                f"UUID normalization recovered fields for {table_name}: {', '.join(recovered)}"
            )
        async with self.engine.begin() as conn:
            await conn.execute(_t(query), normalized)

    async def log_economic_attribution(
        self,
        source_scout: str,
        influence_type: str,
        target_agent: str,
        strategy_id: str | None = None,
        strategy_name: str | None = None,
        sharpe_contribution: float = 0.0,
        drawdown_contribution: float = 0.0,
        pnl_contribution: float = 0.0,
        win_rate_contribution: float = 0.0,
        attribution_weight: float = 0.0,
        survived_validation: bool = False,
        regime_at_time: str | None = None,
        entropy_at_time: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        trace_id = str(uuid.uuid4())
        try:
            await self._execute_insert(
                """
                INSERT INTO scout_economic_attribution
                    (trace_id, source_scout, influence_type, target_agent,
                     strategy_id, strategy_name,
                     sharpe_contribution, drawdown_contribution, pnl_contribution,
                     win_rate_contribution, attribution_weight,
                     survived_validation, regime_at_time, entropy_at_time, metadata)
                VALUES
                    (:trace_id, :source, :itype, :target,
                     :sid, :sname,
                     :sharpe, :dd, :pnl,
                     :wr, :weight,
                     :survived, :regime, :entropy, CAST(:meta AS jsonb))
                """,
                {
                    "trace_id": trace_id,
                    "source": source_scout,
                    "itype": influence_type,
                    "target": target_agent,
                    "sid": strategy_id,
                    "sname": strategy_name,
                    "sharpe": sharpe_contribution,
                    "dd": drawdown_contribution,
                    "pnl": pnl_contribution,
                    "wr": win_rate_contribution,
                    "weight": attribution_weight,
                    "survived": survived_validation,
                    "regime": regime_at_time,
                    "entropy": entropy_at_time,
                    "meta": json.dumps(metadata or {}),
                },
            )
        except Exception as e:
            logger.debug(f"log_economic_attribution failed: {e}")

    async def get_economic_attribution_summary(self, hours: int = 24) -> list[dict]:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                sa_text("""
                    SELECT source_scout,
                           COUNT(*) as n_strategies,
                           AVG(sharpe_contribution) as avg_sharpe,
                           AVG(pnl_contribution) as avg_pnl,
                           SUM(CASE WHEN survived_validation THEN 1 ELSE 0 END) as n_survived,
                           AVG(attribution_weight) as avg_weight
                    FROM scout_economic_attribution
                    WHERE created_at > NOW() - CAST(:hours_str AS INTERVAL)
                    GROUP BY source_scout
                    ORDER BY avg_sharpe DESC
                """),
                {"hours_str": timedelta(hours=hours)},
            )
            rows = result.fetchall()
            return [
                {
                    "source_scout": row[0],
                    "n_strategies": int(row[1]),
                    "avg_sharpe_contribution": float(row[2] or 0),
                    "avg_pnl_contribution": float(row[3] or 0),
                    "n_survived_validation": int(row[4] or 0),
                    "avg_attribution_weight": float(row[5] or 0),
                }
                for row in rows
            ]


class Phase37MetricsCollector:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase37_intelligence_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT,
                    dominant_organisms INT,
                    long_horizon_specialization_score FLOAT,
                    mutation_dominance_score FLOAT,
                    scout_intelligence_score FLOAT,
                    capital_migration_score FLOAT,
                    survival_quality_score FLOAT,
                    perturbation_resilience_score FLOAT,
                    execution_survivability_score FLOAT,
                    diversification_quality FLOAT,
                    regime_adaptation_quality FLOAT,
                    retirement_pressure_score FLOAT,
                    replay_integrity FLOAT,
                    specialization_lineage_history JSONB,
                    mutation_family_rankings JSONB,
                    mutation_survival_curves JSONB,
                    scout_trust_rankings JSONB,
                    scout_specialization_history JSONB,
                    capital_allocation_migration JSONB,
                    survival_quality_evolution JSONB,
                    perturbation_snapshot JSONB,
                    regime_specialization_snapshot JSONB,
                    retirement_snapshot JSONB,
                    execution_realism_snapshot JSONB,
                    metadata JSONB
                )
            """))
            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase37_intelligence_metrics_time
                ON phase37_intelligence_metrics (recorded_at DESC)
            """))
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase37_activation_weights (
                    id SERIAL PRIMARY KEY,
                    learned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    domain_weights JSONB NOT NULL,
                    metadata JSONB
                )
            """))

        logger.info("Phase 37 intelligence metrics tables initialized")

    async def collect(self, runtime_minutes: int) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": runtime_minutes,
            "dominant_organisms": 0,
            "long_horizon_specialization_score": 0.0,
            "mutation_dominance_score": 0.0,
            "scout_intelligence_score": 0.0,
            "capital_migration_score": 0.0,
            "survival_quality_score": 0.0,
            "perturbation_resilience_score": 0.0,
            "execution_survivability_score": 0.0,
            "diversification_quality": 0.0,
            "regime_adaptation_quality": 0.0,
            "retirement_pressure_score": 0.0,
            "replay_integrity": 1.0,
            "specialization_lineage_history": [],
            "mutation_family_rankings": [],
            "mutation_survival_curves": [],
            "scout_trust_rankings": [],
            "scout_specialization_history": [],
            "capital_allocation_migration": {},
            "survival_quality_evolution": {},
            "perturbation_snapshot": {},
            "regime_specialization_snapshot": {},
            "retirement_snapshot": {},
            "execution_realism_snapshot": {},
        }

        async with self.engine.connect() as conn:
            def _coerce_json(value: Any, default: Any) -> Any:
                if value is None:
                    return default
                if isinstance(value, (dict, list, int, float, bool)):
                    return value
                try:
                    return json.loads(value)
                except Exception:
                    return default

            async def safe_scalar(sql: str, default: Any = 0, params: dict[str, Any] | None = None) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).scalar() or default
                except Exception as exc:
                    logger.warning(f"Phase37 metric scalar fallback: {exc}")
                    return default

            async def safe_fetchone(sql: str, params: dict[str, Any] | None = None) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).fetchone()
                except Exception as exc:
                    logger.warning(f"Phase37 metric row fallback: {exc}")
                    return None

            async def safe_fetchall(sql: str, params: dict[str, Any] | None = None) -> list[Any]:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).fetchall()
                except Exception as exc:
                    logger.warning(f"Phase37 metric set fallback: {exc}")
                    return []

            metrics["dominant_organisms"] = int(await safe_scalar(
                "SELECT COALESCE(COUNT(*), 0) FROM strategies WHERE lifecycle_state = 'dominant'",
                0,
            ))
            dominant_latest = await safe_fetchone("""
                SELECT tracked_at, n_organisms_total, n_dominant_identified,
                       dominant_organisms, lifespan_rankings, efficiency_rankings,
                       expectancy_rankings, regime_specialists,
                       mutation_family_resilience, recovery_scores,
                       retirement_cause_distribution, ecosystem_health
                FROM dominant_organism_log
                ORDER BY tracked_at DESC
                LIMIT 1
            """)
            if dominant_latest:
                metrics["specialization_lineage_history"] = _coerce_json(dominant_latest[3], [])
                metrics["mutation_family_rankings"] = _coerce_json(dominant_latest[8], [])
                metrics["regime_specialization_snapshot"] = {
                    "n_organisms_total": int(dominant_latest[1] or 0),
                    "n_dominant_identified": int(dominant_latest[2] or 0),
                    "ecosystem_health": _coerce_json(dominant_latest[11], {}),
                    "regime_specialists": _coerce_json(dominant_latest[7], {}),
                }
                metrics["mutation_dominance_score"] = self._score_mutation_dominance(metrics["mutation_family_rankings"])
                metrics["long_horizon_specialization_score"] = self._score_specialization(metrics["regime_specialization_snapshot"], metrics["mutation_family_rankings"])

            family_rows = await safe_fetchall("""
                WITH latest_fitness AS (
                    SELECT DISTINCT ON (br.strategy_id)
                        br.strategy_id,
                        br.composite_fitness_score,
                        br.sharpe,
                        br.max_drawdown,
                        br.win_rate,
                        br.created_at
                    FROM backtest_results br
                    ORDER BY br.strategy_id, br.created_at DESC
                )
                SELECT
                    m.mutation_type,
                    DATE_TRUNC('day', m.created_at) AS day_bucket,
                    COUNT(*) AS total_applications,
                    COUNT(*) FILTER (WHERE lf.composite_fitness_score > 30) AS survived_count,
                    COALESCE(AVG(lf.composite_fitness_score), 0) AS avg_fitness,
                    COALESCE(AVG(lf.sharpe), 0) AS avg_sharpe,
                    COALESCE(AVG(ABS(lf.max_drawdown)), 0) AS avg_drawdown
                FROM mutation_memory m
                LEFT JOIN latest_fitness lf ON lf.strategy_id = m.child_strategy_id
                WHERE m.created_at > NOW() - INTERVAL '14 days'
                GROUP BY m.mutation_type, DATE_TRUNC('day', m.created_at)
                ORDER BY day_bucket ASC, total_applications DESC
                LIMIT 120
            """)
            metrics["mutation_survival_curves"] = [
                {
                    "mutation_type": str(r[0] or "unknown"),
                    "day": r[1],
                    "total_applications": int(r[2] or 0),
                    "survived_count": int(r[3] or 0),
                    "survival_rate": round((int(r[3] or 0) / max(1, int(r[2] or 0))), 4),
                    "avg_fitness": float(r[4] or 0),
                    "avg_sharpe": float(r[5] or 0),
                    "avg_drawdown": float(r[6] or 0),
                }
                for r in family_rows
            ]

            scout_latest = await safe_fetchone("""
                SELECT tracked_at, n_attributions_analyzed, n_scouts_tracked,
                       profit_contribution, failure_contribution, regime_usefulness,
                       contradiction_penalties, attribution_quality,
                       divergence_scores, ecosystem_scout_health, metadata
                FROM scout_divergence_log
                ORDER BY tracked_at DESC
                LIMIT 1
            """)
            if scout_latest:
                metrics["scout_specialization_history"] = _coerce_json(scout_latest[8], [])
                metrics["scout_trust_rankings"] = self._flatten_scout_trust(metrics["scout_specialization_history"])
                metrics["scout_intelligence_score"] = self._score_scout_intelligence(
                    scout_latest,
                    metrics["scout_trust_rankings"],
                )

            capital_latest = await safe_fetchone("""
                SELECT tracked_at,
                       COALESCE((evolution_pressure_stats->>'total_capital_migrated')::float, 0) AS capital_migrated,
                       COALESCE((evolution_pressure_stats->>'n_weak_penalized')::int, 0) AS weak_penalized,
                       COALESCE((evolution_pressure_stats->>'n_dominant_boosted')::int, 0) AS dominant_boosted,
                       COALESCE((evolution_pressure_stats->>'concentration_risk')::float, 0) AS concentration_risk,
                       COALESCE((evolution_pressure_stats->>'diversification_score')::float, 0) AS diversification_score,
                       COALESCE((evolution_pressure_stats->>'portfolio_survivability')::float, 0) AS portfolio_survivability,
                       COALESCE((evolution_pressure_stats->>'drawdown_recovery_speed')::float, 0) AS drawdown_recovery_speed
                FROM portfolio_evolution_log
                ORDER BY tracked_at DESC
                LIMIT 1
            """)
            if capital_latest:
                metrics["capital_allocation_migration"] = {
                    "tracked_at": capital_latest[0],
                    "capital_migrated": float(capital_latest[1] or 0),
                    "weak_penalized": int(capital_latest[2] or 0),
                    "dominant_boosted": int(capital_latest[3] or 0),
                    "concentration_risk": float(capital_latest[4] or 0),
                    "diversification_score": float(capital_latest[5] or 0),
                    "portfolio_survivability": float(capital_latest[6] or 0),
                    "drawdown_recovery_speed": float(capital_latest[7] or 0),
                }
                metrics["capital_migration_score"] = self._score_capital_migration(metrics["capital_allocation_migration"])
                metrics["diversification_quality"] = max(0.0, min(1.0, float(capital_latest[5] or 0)))

            survival_rows = await safe_fetchall("""
                SELECT analyzed_at,
                       COALESCE(expectancy, 0) AS expectancy,
                       COALESCE(risk_adjusted_return, 0) AS risk_adjusted_return,
                       COALESCE(return_per_drawdown, 0) AS return_per_drawdown,
                       COALESCE(strategy_half_life_hours, 0) AS half_life_hours,
                       COALESCE(mutation_survival_rate, 0) AS mutation_survival_rate,
                       COALESCE(regime_persistence, 0) AS regime_persistence,
                       COALESCE(drawdown_persistence_hours, 0) AS drawdown_persistence_hours,
                       COALESCE(recovery_efficiency, 0) AS recovery_efficiency,
                       COALESCE(cascading_failure_risk, 0) AS cascading_failure_risk,
                       COALESCE(concentration_instability, 0) AS concentration_instability,
                       COALESCE(portfolio_contagion_risk, 0) AS portfolio_contagion_risk,
                       COALESCE(execution_degradation, 0) AS execution_degradation
                FROM economic_efficiency_analysis
                WHERE analyzed_at > NOW() - INTERVAL '14 days'
                ORDER BY analyzed_at ASC
                LIMIT 200
            """)
            metrics["survival_quality_evolution"] = self._build_survival_evolution(survival_rows)
            metrics["survival_quality_score"] = self._score_survival_quality(metrics["survival_quality_evolution"])

            retirement_latest = await safe_fetchone("""
                SELECT analyzed_at, n_strategies_analyzed, n_active, n_monitor,
                       n_retirement_pending, n_retired,
                       retirement_recommendations, capital_withdrawal_signals
                FROM strategy_retirement
                ORDER BY analyzed_at DESC
                LIMIT 1
            """)
            if retirement_latest:
                metrics["retirement_snapshot"] = {
                    "analyzed_at": retirement_latest[0],
                    "n_strategies_analyzed": int(retirement_latest[1] or 0),
                    "n_active": int(retirement_latest[2] or 0),
                    "n_monitor": int(retirement_latest[3] or 0),
                    "n_retirement_pending": int(retirement_latest[4] or 0),
                    "n_retired": int(retirement_latest[5] or 0),
                    "retirement_recommendations": _coerce_json(retirement_latest[6], []),
                    "capital_withdrawal_signals": _coerce_json(retirement_latest[7], []),
                }
                metrics["retirement_pressure_score"] = self._score_retirement_pressure(metrics["retirement_snapshot"])

            exec_row = await safe_fetchone("""
                SELECT COALESCE(execution_degradation_score, 0),
                       COALESCE(avg_expected_slippage_bps, 0),
                       COALESCE(avg_fill_probability, 0)
                FROM execution_realism
                ORDER BY simulated_at DESC
                LIMIT 1
            """)
            if exec_row:
                metrics["execution_realism_snapshot"] = {
                    "execution_degradation_score": float(exec_row[0] or 0),
                    "avg_expected_slippage_bps": float(exec_row[1] or 0),
                    "avg_fill_probability": float(exec_row[2] or 0),
                }
                metrics["execution_survivability_score"] = max(0.0, min(1.0, 1.0 - float(exec_row[0] or 0)))

            drift_row = await safe_fetchone("""
                SELECT COALESCE(composite_severity, 0),
                       COALESCE(feature_drift_score, 0),
                       COALESCE(strategy_drift_score, 0),
                       COALESCE(regime_drift_score, 0),
                       COALESCE(execution_drift_score, 0)
                FROM drift_detection
                ORDER BY detected_at DESC
                LIMIT 1
            """)
            drift_severity = float(drift_row[0] or 0) if drift_row else 0.0
            metrics["perturbation_snapshot"] = {
                "active_perturbations": [
                    {
                        "type": p.get("type"),
                        "severity": p.get("severity"),
                        "duration_minutes": p.get("duration_minutes"),
                        "category": p.get("category"),
                    }
                    for p in getattr(self, "_perturbation_state", [])
                ],
                "drift_severity": drift_severity,
                "strategy_drift_score": float(drift_row[2] or 0) if drift_row else 0.0,
                "regime_drift_score": float(drift_row[3] or 0) if drift_row else 0.0,
                "execution_drift_score": float(drift_row[4] or 0) if drift_row else 0.0,
            }
            metrics["perturbation_resilience_score"] = max(0.0, min(1.0, 1.0 - drift_severity))

            replay_row = await safe_fetchone("""
                SELECT COALESCE(integrity_score, 100)
                FROM replay_integrity
                ORDER BY checked_at DESC
                LIMIT 1
            """)
            replay_score = float(replay_row[0] or 100.0) if replay_row else 100.0
            metrics["replay_integrity"] = replay_score / 100.0 if replay_score > 1 else replay_score

            metrics["regime_adaptation_quality"] = self._score_regime_adaptation(
                metrics["regime_specialization_snapshot"],
                metrics["mutation_family_rankings"],
                metrics.get("runtime_minutes", 0),
            )

        self._compute_composites(metrics)
        await self._persist(metrics)
        await self._update_domain_weights(metrics)
        self.metrics_history.append(metrics)
        return metrics

    def _score_mutation_dominance(self, rankings: list[dict]) -> float:
        if not rankings:
            return 0.0
        top = rankings[:5]
        survival = sum(float(r.get("survival_rate", 0)) for r in top) / max(1, len(top))
        fitness = sum(float(r.get("avg_fitness_contribution", 0)) for r in top) / max(1, len(top))
        return round(max(0.0, min(1.0, 0.6 * survival + 0.4 * min(1.0, fitness / 100.0))), 4)

    def _score_specialization(self, regime_snapshot: dict, mutation_rankings: list[dict]) -> float:
        regime_specialists = regime_snapshot.get("regime_specialists", {}) if isinstance(regime_snapshot, dict) else {}
        n_specialists = len(regime_specialists)
        n_dominant = int(regime_snapshot.get("n_dominant_identified", 0) or 0) if isinstance(regime_snapshot, dict) else 0
        mutation_bonus = self._score_mutation_dominance(mutation_rankings)
        return round(max(0.0, min(1.0, 0.45 * min(1.0, n_specialists / 5.0) + 0.35 * min(1.0, n_dominant / 10.0) + 0.20 * mutation_bonus)), 4)

    def _flatten_scout_trust(self, history: list[dict]) -> list[dict]:
        trust_rows = []
        for item in history[:20]:
            if not isinstance(item, dict):
                continue
            trust_rows.append({
                "scout_name": item.get("scout_name", "unknown"),
                "composite_divergence_score": float(item.get("composite_divergence_score", 0) or 0),
                "net_contribution": float(item.get("net_contribution", 0) or 0),
                "n_profitable": int(item.get("n_profitable", 0) or 0),
                "n_failed": int(item.get("n_failed", 0) or 0),
                "total_attributions": int(item.get("total_attributions", 0) or 0),
            })
        trust_rows.sort(key=lambda x: (-x["composite_divergence_score"], -x["net_contribution"]))
        return trust_rows

    def _score_scout_intelligence(self, scout_latest: Any, trust_rows: list[dict]) -> float:
        if not trust_rows:
            return 0.0
        top = trust_rows[:5]
        useful = sum(max(0.0, row.get("net_contribution", 0)) for row in top) / max(1, len(top))
        diversity = len({row.get("scout_name", "") for row in top}) / max(1, len(top))
        return round(max(0.0, min(1.0, 0.7 * min(1.0, useful + 0.5) + 0.3 * diversity)), 4)

    def _score_capital_migration(self, capital: dict) -> float:
        if not capital:
            return 0.0
        migrated = float(capital.get("capital_migrated", 0) or 0)
        concentration_risk = float(capital.get("concentration_risk", 0) or 0)
        diversification = float(capital.get("diversification_score", 0) or 0)
        survivability = float(capital.get("portfolio_survivability", 0) or 0)
        recovery = float(capital.get("drawdown_recovery_speed", 0) or 0)
        return round(max(0.0, min(1.0,
            0.25 * min(1.0, migrated)
            + 0.20 * max(0.0, 1.0 - concentration_risk)
            + 0.20 * max(0.0, diversification)
            + 0.20 * max(0.0, survivability)
            + 0.15 * max(0.0, min(1.0, recovery))
        )), 4)

    def _build_survival_evolution(self, rows: list[Any]) -> dict:
        if not rows:
            return {}
        normalized = []
        for r in rows:
            normalized.append({
                "analyzed_at": r[0],
                "expectancy": float(r[1] or 0),
                "risk_adjusted_return": float(r[2] or 0),
                "return_per_drawdown": float(r[3] or 0),
                "half_life_hours": float(r[4] or 0),
                "mutation_survival_rate": float(r[5] or 0),
                "regime_persistence": float(r[6] or 0),
                "drawdown_persistence_hours": float(r[7] or 0),
                "recovery_efficiency": float(r[8] or 0),
                "cascading_failure_risk": float(r[9] or 0),
                "concentration_instability": float(r[10] or 0),
                "portfolio_contagion_risk": float(r[11] or 0),
                "execution_degradation": float(r[12] or 0),
            })
        midpoint = max(1, len(normalized) // 2)
        early = normalized[:midpoint]
        late = normalized[midpoint:]
        return {
            "n_points": len(normalized),
            "early": self._avg_survival_window(early),
            "late": self._avg_survival_window(late),
            "trend": self._trend_delta(self._avg_survival_window(early), self._avg_survival_window(late)),
            "timeline": normalized[:30],
        }

    def _avg_survival_window(self, rows: list[dict]) -> dict:
        if not rows:
            return {}
        return {
            "expectancy": sum(r["expectancy"] for r in rows) / len(rows),
            "risk_adjusted_return": sum(r["risk_adjusted_return"] for r in rows) / len(rows),
            "return_per_drawdown": sum(r["return_per_drawdown"] for r in rows) / len(rows),
            "half_life_hours": sum(r["half_life_hours"] for r in rows) / len(rows),
            "mutation_survival_rate": sum(r["mutation_survival_rate"] for r in rows) / len(rows),
            "regime_persistence": sum(r["regime_persistence"] for r in rows) / len(rows),
            "drawdown_persistence_hours": sum(r["drawdown_persistence_hours"] for r in rows) / len(rows),
            "recovery_efficiency": sum(r["recovery_efficiency"] for r in rows) / len(rows),
            "cascading_failure_risk": sum(r["cascading_failure_risk"] for r in rows) / len(rows),
            "concentration_instability": sum(r["concentration_instability"] for r in rows) / len(rows),
            "portfolio_contagion_risk": sum(r["portfolio_contagion_risk"] for r in rows) / len(rows),
            "execution_degradation": sum(r["execution_degradation"] for r in rows) / len(rows),
        }

    def _trend_delta(self, early: dict, late: dict) -> dict:
        if not early or not late:
            return {}
        keys = set(early.keys()) & set(late.keys())
        out = {}
        for key in keys:
            a = float(early.get(key, 0) or 0)
            b = float(late.get(key, 0) or 0)
            out[key] = round((b - a) / abs(a), 4) if a else round(b, 4)
        return out

    def _score_survival_quality(self, evolution: dict) -> float:
        if not evolution:
            return 0.0
        early = evolution.get("early", {})
        late = evolution.get("late", {})
        expectancy_gain = float(late.get("expectancy", 0) or 0) - float(early.get("expectancy", 0) or 0)
        recovery_gain = float(late.get("recovery_efficiency", 0) or 0) - float(early.get("recovery_efficiency", 0) or 0)
        drawdown_gain = float(early.get("cascading_failure_risk", 0) or 0) - float(late.get("cascading_failure_risk", 0) or 0)
        return round(max(0.0, min(1.0, 0.4 * max(0.0, expectancy_gain + 0.5) + 0.3 * max(0.0, recovery_gain + 0.5) + 0.3 * max(0.0, drawdown_gain + 0.5))), 4)

    def _score_retirement_pressure(self, snapshot: dict) -> float:
        if not snapshot:
            return 0.0
        n_pending = int(snapshot.get("n_retirement_pending", 0) or 0)
        n_retired = int(snapshot.get("n_retired", 0) or 0)
        n_total = int(snapshot.get("n_strategies_analyzed", 0) or 0)
        return round(max(0.0, min(1.0, (n_pending + n_retired) / max(1, n_total))), 4)

    def _score_regime_adaptation(self, snapshot: dict, mutation_rankings: list[dict], duration_minutes: int) -> float | None:
        # Minimum duration guard: regime analysis is unreliable for short runs
        if duration_minutes is None or int(duration_minutes) < 10:
            logger.warning(
                "Regime analysis requires minimum 10 minutes. "
                f"Got {duration_minutes}min. Score will be unreliable."
            )
            return None

        regimes = snapshot.get("regime_specialists", {}) if isinstance(snapshot, dict) else {}
        n_regimes = len(regimes)
        health = snapshot.get("ecosystem_health", {}) if isinstance(snapshot, dict) else {}
        dominant = int(health.get("n_dominant_organisms", 0) or 0)
        mutation_bonus = self._score_mutation_dominance(mutation_rankings)
        return round(max(0.0, min(1.0, 0.5 * min(1.0, n_regimes / 5.0) + 0.25 * min(1.0, dominant / 10.0) + 0.25 * mutation_bonus)), 4)

    def _compute_composites(self, metrics: dict[str, Any]) -> None:
        specialization = float(metrics.get("long_horizon_specialization_score", 0) or 0)
        mutation = float(metrics.get("mutation_dominance_score", 0) or 0)
        scout = float(metrics.get("scout_intelligence_score", 0) or 0)
        capital = float(metrics.get("capital_migration_score", 0) or 0)
        survival = float(metrics.get("survival_quality_score", 0) or 0)
        perturbation = float(metrics.get("perturbation_resilience_score", 0) or 0)
        execution = float(metrics.get("execution_survivability_score", 0) or 0)
        diversification = float(metrics.get("diversification_quality", 0) or 0)
        raw_regime = metrics.get("regime_adaptation_quality", 0)
        # Preserve explicit None for regime_adaptation_quality (insufficient duration)
        if raw_regime is None:
            regime = 0.0
            preserve_regime_none = True
        else:
            regime = float(raw_regime or 0)
            preserve_regime_none = False
        replay = float(metrics.get("replay_integrity", 1.0) or 1.0)
        retirement = float(metrics.get("retirement_pressure_score", 0) or 0)

        metrics["long_horizon_specialization_score"] = round(max(0.0, min(1.0, specialization)), 4)
        metrics["mutation_dominance_score"] = round(max(0.0, min(1.0, mutation)), 4)
        metrics["scout_intelligence_score"] = round(max(0.0, min(1.0, scout)), 4)
        metrics["capital_migration_score"] = round(max(0.0, min(1.0, capital)), 4)
        metrics["survival_quality_score"] = round(max(0.0, min(1.0, survival)), 4)
        metrics["perturbation_resilience_score"] = round(max(0.0, min(1.0, perturbation)), 4)
        metrics["execution_survivability_score"] = round(max(0.0, min(1.0, execution)), 4)
        metrics["diversification_quality"] = round(max(0.0, min(1.0, diversification)), 4)
        if not preserve_regime_none:
            metrics["regime_adaptation_quality"] = round(max(0.0, min(1.0, regime)), 4)
        metrics["retirement_pressure_score"] = round(max(0.0, min(1.0, retirement)), 4)
        metrics["replay_integrity"] = round(max(0.0, min(1.0, replay)), 4)

        metrics["long_horizon_intelligence_score"] = round(max(0.0, min(1.0,
            0.14 * metrics["long_horizon_specialization_score"]
            + 0.12 * metrics["mutation_dominance_score"]
            + 0.14 * metrics["scout_intelligence_score"]
            + 0.12 * metrics["capital_migration_score"]
            + 0.14 * metrics["survival_quality_score"]
            + 0.10 * metrics["perturbation_resilience_score"]
            + 0.10 * metrics["execution_survivability_score"]
            + 0.08 * metrics["diversification_quality"]
            + 0.08 * regime
            + 0.08 * metrics["replay_integrity"]
        )), 4)

    async def _persist(self, metrics: dict[str, Any]) -> None:
        def _dump_json(value: Any) -> str:
            return json.dumps(value, default=str)

        payload = {
            **metrics,
            "specialization_lineage_history": _dump_json(metrics["specialization_lineage_history"]),
            "mutation_family_rankings": _dump_json(metrics["mutation_family_rankings"]),
            "mutation_survival_curves": _dump_json(metrics["mutation_survival_curves"]),
            "scout_trust_rankings": _dump_json(metrics["scout_trust_rankings"]),
            "scout_specialization_history": _dump_json(metrics["scout_specialization_history"]),
            "capital_allocation_migration": _dump_json(metrics["capital_allocation_migration"]),
            "survival_quality_evolution": _dump_json(metrics["survival_quality_evolution"]),
            "perturbation_snapshot": _dump_json(metrics["perturbation_snapshot"]),
            "regime_specialization_snapshot": _dump_json(metrics["regime_specialization_snapshot"]),
            "retirement_snapshot": _dump_json(metrics["retirement_snapshot"]),
            "execution_realism_snapshot": _dump_json(metrics["execution_realism_snapshot"]),
            "metadata": _dump_json({"collected_at": datetime.now(timezone.utc)}),
        }
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase37_intelligence_metrics (
                    recorded_at, runtime_minutes,
                    dominant_organisms, long_horizon_specialization_score,
                    mutation_dominance_score, scout_intelligence_score,
                    capital_migration_score, survival_quality_score,
                    perturbation_resilience_score, execution_survivability_score,
                    diversification_quality, regime_adaptation_quality,
                    retirement_pressure_score, replay_integrity,
                    specialization_lineage_history, mutation_family_rankings,
                    mutation_survival_curves, scout_trust_rankings,
                    scout_specialization_history, capital_allocation_migration,
                    survival_quality_evolution, perturbation_snapshot,
                    regime_specialization_snapshot, retirement_snapshot,
                    execution_realism_snapshot, metadata
                ) VALUES (
                    :recorded_at, :runtime_minutes,
                    :dominant_organisms, :long_horizon_specialization_score,
                    :mutation_dominance_score, :scout_intelligence_score,
                    :capital_migration_score, :survival_quality_score,
                    :perturbation_resilience_score, :execution_survivability_score,
                    :diversification_quality, :regime_adaptation_quality,
                    :retirement_pressure_score, :replay_integrity,
                    CAST(:specialization_lineage_history AS jsonb), CAST(:mutation_family_rankings AS jsonb),
                    CAST(:mutation_survival_curves AS jsonb), CAST(:scout_trust_rankings AS jsonb),
                    CAST(:scout_specialization_history AS jsonb), CAST(:capital_allocation_migration AS jsonb),
                    CAST(:survival_quality_evolution AS jsonb), CAST(:perturbation_snapshot AS jsonb),
                    CAST(:regime_specialization_snapshot AS jsonb), CAST(:retirement_snapshot AS jsonb),
                    CAST(:execution_realism_snapshot AS jsonb), CAST(:metadata AS jsonb)
                )
            """), payload)

    async def _update_domain_weights(self, metrics: dict[str, Any]) -> None:
        def _as_float(value: Any) -> float:
            return float(value) if value is not None else 0.0

        weights = {
            "specialization": _as_float(metrics.get("long_horizon_specialization_score")),
            "mutation": _as_float(metrics.get("mutation_dominance_score")),
            "scout": _as_float(metrics.get("scout_intelligence_score")),
            "capital": _as_float(metrics.get("capital_migration_score")),
            "survival": _as_float(metrics.get("survival_quality_score")),
            "perturbation": _as_float(metrics.get("perturbation_resilience_score")),
            "execution": _as_float(metrics.get("execution_survivability_score")),
            "regime": _as_float(metrics.get("regime_adaptation_quality")),
        }
        total = sum(max(0.0, v) for v in weights.values())
        if total <= 0:
            normalized = {k: 1.0 / len(weights) for k in weights}
        else:
            normalized = {k: max(0.0, v) / total for k, v in weights.items()}

        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase37_activation_weights (domain_weights, metadata)
                VALUES (CAST(:weights AS jsonb), CAST(:metadata AS jsonb))
            """), {
                "weights": json.dumps(normalized),
                "metadata": json.dumps({"source": "phase37_long_horizon_intelligence"}),
            })

    async def close(self) -> None:
        await self.engine.dispose()


class Phase37LongHorizonController:
    def __init__(self, duration_minutes: int = 720, metrics_interval: int = 300):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = metrics_interval
        self.db_url = settings.database_url
        self.metrics = Phase37MetricsCollector(self.db_url)
        self._shutdown = False
        self._start_time: Optional[float] = None

        self._soak_db: Optional[SoakDbClient] = None
        self._engines_initialized = False
        self._dominant_tracker = None
        self._lineage_tracker = None
        self._regime_engine = None
        self._scout_engine = None
        self._portfolio_engine = None
        self._stress_engine = None
        self._mutation_policy = None
        self._economic_engine = None
        self._retirement_engine = None
        self._replay_engine = None
        self._feature_engine = None
        self._synthesis_engine = None
        self._hypothesis_engine = None
        self._copy_engine = None
        self._attribution_engine = None
        self._failure_engine = None
        self._drift_engine = None
        self._perturbation_state: list[dict[str, Any]] = []

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
        self._stress_engine = RegimeStressEngine(redis_client=None, db_client=self._soak_db)
        self._mutation_policy = MutationPolicyEngine(redis_client=None, db_client=self._soak_db)
        self._economic_engine = EconomicEfficiencyEngine(redis_client=None, db_client=self._soak_db)
        self._retirement_engine = StrategyRetirementEngine(redis_client=None, db_client=self._soak_db, run_interval=3600)
        self._replay_engine = ReplayEngine(redis_client=None, db_client=self._soak_db)
        self._feature_engine = FeatureEvolutionEngine(redis_client=None, db_client=self._soak_db)
        self._synthesis_engine = ScoutSynthesisEngine(redis_client=None, db_client=self._soak_db)
        self._hypothesis_engine = HypothesisEngine(redis_client=None, db_client=self._soak_db)
        self._copy_engine = CopyAnalyticsEngine(redis_client=None, db_client=self._soak_db)
        self._attribution_engine = EconomicAttributionEngine(redis_client=None, db_client=self._soak_db)
        self._failure_engine = FailureAnalysisEngine(redis_client=None, db_client=self._soak_db)
        self._drift_engine = DriftDetectionEngine(redis_client=None, db_client=self._soak_db)

        # Provide a GovernanceExecutionContext to engines so they consume
        # canonical governance IDs instead of self-generating them.
        exec_ctx = GovernanceExecutionContext(governance_mode=os.getenv("ATLAS_GOVERNANCE_MODE", "shadow"))
        for eng in (
            self._dominant_tracker,
            self._lineage_tracker,
            self._regime_engine,
            self._scout_engine,
            self._portfolio_engine,
            self._stress_engine,
            self._mutation_policy,
            self._economic_engine,
            self._retirement_engine,
            self._replay_engine,
            self._feature_engine,
            self._synthesis_engine,
            self._hypothesis_engine,
            self._copy_engine,
            self._attribution_engine,
            self._failure_engine,
            self._drift_engine,
        ):
            try:
                setattr(eng, "execution_context", exec_ctx)
            except Exception:
                # best-effort assignment; engines may ignore it
                pass

        self._engines_initialized = True
        logger.info("Phase 37 engines initialized")

    async def _safe_call(self, name: str, coro, timeout: int = 60) -> None:
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.debug(f"Phase37[{name}] OK")
        except asyncio.TimeoutError:
            logger.warning(f"Phase37[{name}] TIMEOUT after {timeout}s")
        except Exception as e:
            logger.warning(f"Phase37[{name}] FAILED: {type(e).__name__}: {e}")

    async def _run_phase37_cycle(self) -> None:
        await self._safe_call("DominantOrganism", self._dominant_tracker._tracking_cycle())
        await self._safe_call("MutationLineage", self._lineage_tracker._lineage_cycle())
        await self._safe_call("RegimeSpecialization", self._regime_engine._profiling_cycle())
        await self._safe_call("ScoutDivergence", self._scout_engine._divergence_cycle())
        await self._safe_call("PortfolioEvolution", self._portfolio_engine._pressure_cycle())
        await self._safe_call("RegimeStress", self._stress_engine._stress_cycle())
        self._perturbation_state = list(getattr(self._stress_engine, "_active_perturbations", []))
        await self._safe_call("MutationPolicy", self._mutation_policy._learn_policy())
        await self._safe_call("EconomicEfficiency", self._economic_engine._full_economic_analysis_cycle())
        await self._safe_call("ReplayIntegrity", self._replay_engine._sweep_replay_checks())
        await self._safe_call("FeatureEvolution", self._feature_engine._evolve_features())
        await self._safe_call("ScoutSynthesis", self._synthesis_engine._synthesis_cycle())
        await self._safe_call("Hypothesis", self._hypothesis_engine._hypothesis_cycle())
        await self._safe_call("CopyAnalytics", self._copy_engine._compute_analytics())
        await self._safe_call("EconomicAttribution", self._attribution_engine._attribution_cycle())
        await self._safe_call("FailureAnalysis", self._failure_engine._analysis_cycle())

        drift_report = await self._drift_engine._compute_drift_report()
        if drift_report:
            await self._safe_call("DriftPersist", self._drift_engine._persist_drift(drift_report))
            await self._safe_call("DriftPublish", self._drift_engine._publish_drift(drift_report))
            if drift_report.get("retirement_candidates"):
                await self._safe_call("DriftRetirementNotify", self._drift_engine._notify_retirement(drift_report["retirement_candidates"]))

        retirement_report = await self._retirement_engine._compute_retirement_analysis()
        if retirement_report:
            await self._safe_call("RetirementPersist", self._retirement_engine._persist_retirement(retirement_report))
            await self._safe_call("RetirementPublish", self._retirement_engine._publish_retirement(retirement_report))

    async def _ensure_schema_compatibility(self, probe: TimescaleClient) -> None:
        async with probe.engine.begin() as conn:
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS portfolio_id TEXT"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS diversification_score FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS correlation_collapse_risk FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS contagion_exposure FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS concentration_risk FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS portfolio_survivability FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS drawdown_recovery_speed FLOAT DEFAULT 0"))
            await conn.execute(sa_text("ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS active_strategies INT DEFAULT 0"))

    async def run(self) -> None:
        logger.info("=" * 72)
        logger.info("PHASE 37 - LONG-HORIZON ADAPTIVE INTELLIGENCE EVOLUTION SOAK STARTING")
        logger.info(f"Duration: {self.duration_minutes}m | Metrics interval: {self.metrics_interval}s")
        logger.info("=" * 72)

        schema_probe = TimescaleClient(self.db_url)
        await schema_probe.connect()
        await self._ensure_schema_compatibility(schema_probe)
        await schema_probe.validate_schema_contracts(strict=True)
        await schema_probe.close()

        await self.metrics.initialize()
        await self._ensure_engines()

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
                await self._run_phase37_cycle()
                metrics = await self.metrics.collect(elapsed_minutes)
                self._print_status(metrics, elapsed, remaining)
                await asyncio.sleep(min(self.metrics_interval, remaining))
        finally:
            await self._finalize()

    def _request_shutdown(self) -> None:
        self._shutdown = True

    def _print_status(self, metrics: dict[str, Any], elapsed: float, remaining: float) -> None:
        e = int(elapsed / 60)
        r = int(remaining / 60)
        print(f"\n[Phase37] T+{e}m / T-{r}m")
        print(
            "  Scores: "
            f"LH={metrics.get('long_horizon_specialization_score', 0):.3f} "
            f"MD={metrics.get('mutation_dominance_score', 0):.3f} "
            f"SC={metrics.get('scout_intelligence_score', 0):.3f} "
            f"CM={metrics.get('capital_migration_score', 0):.3f} "
            f"SQ={metrics.get('survival_quality_score', 0):.3f} "
            f"PR={metrics.get('perturbation_resilience_score', 0):.3f} "
            f"ES={metrics.get('execution_survivability_score', 0):.3f} "
            f"RI={metrics.get('replay_integrity', 0):.3f} "
            f"LI={metrics.get('long_horizon_intelligence_score', 0):.3f}"
        )
        print(
            "  Core: "
            f"dominant={metrics.get('dominant_organisms', 0)} "
            f"mutations={len(metrics.get('mutation_family_rankings', []))} "
            f"scouts={len(metrics.get('scout_trust_rankings', []))} "
            f"perturbations={len(self._perturbation_state)}"
        )
        sys.stdout.flush()

    async def _finalize(self) -> None:
        total_minutes = int((time.time() - self._start_time) / 60) if self._start_time else 0
        logger.info(f"Phase 37 soak complete after {total_minutes} minutes")

        latest = self.metrics.metrics_history[-1] if self.metrics.metrics_history else {}
        initial = self.metrics.metrics_history[0] if self.metrics.metrics_history else {}

        # Support `_generate_reports` being either sync or async (PHASE37A monkeypatches it sometimes).
        result = self._generate_reports(initial, latest, total_minutes)
        if inspect.isawaitable(result):
            await result

        await self.metrics.close()

    def _trend_delta(self, initial: dict[str, Any], latest: dict[str, Any], key: str) -> float:
        a = float(initial.get(key, 0) or 0)
        b = float(latest.get(key, 0) or 0)
        if a == 0:
            return b
        return (b - a) / abs(a)

    async def _generate_reports(self, initial: dict[str, Any], latest: dict[str, Any], duration_minutes: int) -> None:
        def _dump_json(value: Any) -> str:
            return json.dumps(value, indent=2, default=str)

        def score_block(title: str, metric_name: str, body: str) -> list[str]:
            return [f"# {title}", "", f"{metric_name}: {latest.get(metric_name.lower().replace(' ', '_'), 0)}", body]

        specialization_lines = [
            "# PHASE37_SPECIALIZATION_EVOLUTION_REPORT",
            "",
            f"Duration minutes: {duration_minutes}",
            f"Long-horizon specialization score: {latest.get('long_horizon_specialization_score', 0)}",
            f"Regime adaptation quality: {latest.get('regime_adaptation_quality', 0)}",
            f"Dominant organisms: {latest.get('dominant_organisms', 0)}",
            f"Specialization lineage history: {_dump_json(latest.get('specialization_lineage_history', [])[:10])}",
            f"Regime specialization snapshot: {_dump_json(latest.get('regime_specialization_snapshot', {}))}",
        ]

        mutation_lines = [
            "# PHASE37_MUTATION_DOMINANCE_REPORT",
            "",
            f"Mutation dominance score: {latest.get('mutation_dominance_score', 0)}",
            f"Mutation family rankings: {_dump_json(latest.get('mutation_family_rankings', [])[:15])}",
            f"Mutation survival curves: {_dump_json(latest.get('mutation_survival_curves', [])[:20])}",
        ]

        scout_lines = [
            "# PHASE37_SCOUT_INTELLIGENCE_REPORT",
            "",
            f"Scout intelligence score: {latest.get('scout_intelligence_score', 0)}",
            f"Scout trust rankings: {_dump_json(latest.get('scout_trust_rankings', [])[:15])}",
            f"Scout specialization history: {_dump_json(latest.get('scout_specialization_history', [])[:15])}",
        ]

        capital_lines = [
            "# PHASE37_CAPITAL_MIGRATION_REPORT",
            "",
            f"Capital migration score: {latest.get('capital_migration_score', 0)}",
            f"Capital allocation migration: {_dump_json(latest.get('capital_allocation_migration', {}))}",
            f"Diversification quality: {latest.get('diversification_quality', 0)}",
        ]

        survival_lines = [
            "# PHASE37_SURVIVAL_QUALITY_REPORT",
            "",
            f"Survival quality score: {latest.get('survival_quality_score', 0)}",
            f"Survival quality evolution: {_dump_json(latest.get('survival_quality_evolution', {}))}",
            f"Execution survivability score: {latest.get('execution_survivability_score', 0)}",
            f"Replay integrity: {latest.get('replay_integrity', 0)}",
        ]

        perturbation_lines = [
            "# PHASE37_REGIME_PERTURBATION_REPORT",
            "",
            f"Perturbation resilience score: {latest.get('perturbation_resilience_score', 0)}",
            f"Perturbation snapshot: {_dump_json(latest.get('perturbation_snapshot', {}))}",
            f"Retirement pressure score: {latest.get('retirement_pressure_score', 0)}",
            f"Retirement snapshot: {_dump_json(latest.get('retirement_snapshot', {}))}",
        ]

        pass_checks = {
            "dominant organisms emerge": latest.get("dominant_organisms", 0) >= 1,
            "mutation families diverge": len(latest.get("mutation_family_rankings", [])) >= 1,
            "scout trust diverges": len(latest.get("scout_trust_rankings", [])) >= 1,
            "regime specialists emerge": latest.get("long_horizon_specialization_score", 0) >= 0.20,
            "adaptive capital migration visible": latest.get("capital_migration_score", 0) >= 0.20,
            "late-generation quality improves": self._trend_delta(initial, latest, "survival_quality_score") >= 0,
            "drawdown resilience improves": self._trend_delta(initial, latest, "survival_quality_score") >= 0,
            "specialization persistence increases": self._trend_delta(initial, latest, "long_horizon_specialization_score") >= 0,
            "replay integrity stable": latest.get("replay_integrity", 0) >= 0.999,
            "ecosystem adapts under pressure": latest.get("perturbation_resilience_score", 0) >= 0.20,
        }
        passed = all(pass_checks.values())

        cert_lines = [
            "# PHASE37_LONG_HORIZON_CERTIFICATION",
            "",
            f"Certification status: {'PASS' if passed else 'PENDING'}",
            "",
            "Checks:",
        ]
        cert_lines.extend([f"- {k}: {'PASS' if v else 'PENDING'}" for k, v in pass_checks.items()])
        cert_lines.extend([
            "",
            "Final scores:",
            json.dumps(
                {
                    "long_horizon_specialization_score": latest.get("long_horizon_specialization_score", 0),
                    "mutation_dominance_score": latest.get("mutation_dominance_score", 0),
                    "scout_intelligence_score": latest.get("scout_intelligence_score", 0),
                    "capital_migration_score": latest.get("capital_migration_score", 0),
                    "survival_quality_score": latest.get("survival_quality_score", 0),
                    "perturbation_resilience_score": latest.get("perturbation_resilience_score", 0),
                    "execution_survivability_score": latest.get("execution_survivability_score", 0),
                    "diversification_quality": latest.get("diversification_quality", 0),
                    "regime_adaptation_quality": latest.get("regime_adaptation_quality", 0),
                    "retirement_pressure_score": latest.get("retirement_pressure_score", 0),
                    "replay_integrity": latest.get("replay_integrity", 0),
                    "long_horizon_intelligence_score": latest.get("long_horizon_intelligence_score", 0),
                },
                indent=2,
                default=str,
            ),
        ])

        reports = {
            "PHASE37_SPECIALIZATION_EVOLUTION_REPORT.md": "\n".join(specialization_lines) + "\n",
            "PHASE37_MUTATION_DOMINANCE_REPORT.md": "\n".join(mutation_lines) + "\n",
            "PHASE37_SCOUT_INTELLIGENCE_REPORT.md": "\n".join(scout_lines) + "\n",
            "PHASE37_CAPITAL_MIGRATION_REPORT.md": "\n".join(capital_lines) + "\n",
            "PHASE37_SURVIVAL_QUALITY_REPORT.md": "\n".join(survival_lines) + "\n",
            "PHASE37_REGIME_PERTURBATION_REPORT.md": "\n".join(perturbation_lines) + "\n",
            "PHASE37_LONG_HORIZON_CERTIFICATION.md": "\n".join(cert_lines) + "\n",
        }

        for name, content in reports.items():
            (ROOT / name).write_text(content, encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 37 long-horizon adaptive intelligence evolution")
    parser.add_argument("--duration-minutes", type=int, default=720)
    parser.add_argument("--metrics-interval", type=int, default=300)
    args = parser.parse_args()

    controller = Phase37LongHorizonController(
        duration_minutes=args.duration_minutes,
        metrics_interval=args.metrics_interval,
    )
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
