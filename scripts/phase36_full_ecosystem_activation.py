"""
phase36_full_ecosystem_activation.py - Phase 36 Full Ecosystem Activation Soak.

Usage:
    python scripts/phase36_full_ecosystem_activation.py --duration-minutes 720
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas.config.settings import settings
from atlas.core.persistence_integrity import normalize_uuid_params
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.governance.context import GovernanceExecutionContext
import os

from atlas.agents.l6_portfolio.portfolio_evolution_pressure import PortfolioEvolutionPressure
from atlas.agents.l2_strategy.coder_agent import CoderAgent
from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2
from atlas.agents.l2_strategy.strategy_normalizer import compute_strategy_signature
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent
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
            context="Phase36SoakDbClient._execute_insert",
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


class Phase36MetricsCollector:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase36_full_ecosystem_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT,
                    execution_activation_score FLOAT,
                    execution_realism_score FLOAT,
                    scout_ecosystem_score FLOAT,
                    advanced_validation_score FLOAT,
                    specialization_score FLOAT,
                    observability_score FLOAT,
                    economic_circulation_score FLOAT,
                    full_activation_score FLOAT,
                    dominant_organisms INT,
                    specialization_rankings JSONB,
                    scout_rankings JSONB,
                    copy_quality_rankings JSONB,
                    validation_snapshot JSONB,
                    observability_snapshot JSONB,
                    economic_circulation_snapshot JSONB,
                    drift_snapshot JSONB,
                    retirement_snapshot JSONB,
                    metadata JSONB
                )
            """))
            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase36_full_ecosystem_metrics_time
                ON phase36_full_ecosystem_metrics (recorded_at DESC)
            """))
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase36_activation_weights (
                    id SERIAL PRIMARY KEY,
                    learned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    domain_weights JSONB NOT NULL,
                    metadata JSONB
                )
            """))

        logger.info("Phase 36 ecosystem metrics tables initialized")

    async def collect(self, runtime_minutes: int) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": runtime_minutes,
            "execution_activation_score": 0.0,
            "execution_realism_score": 0.0,
            "scout_ecosystem_score": 0.0,
            "advanced_validation_score": 0.0,
            "specialization_score": 0.0,
            "observability_score": 0.0,
            "economic_circulation_score": 0.0,
            "full_activation_score": 0.0,
            "dominant_organisms": 0,
            "specialization_rankings": [],
            "scout_rankings": [],
            "copy_quality_rankings": [],
            "validation_snapshot": {},
            "observability_snapshot": {},
            "economic_circulation_snapshot": {},
            "drift_snapshot": {},
            "retirement_snapshot": {},
        }

        async with self.engine.connect() as conn:
            async def safe_scalar(sql: str, default: Any = 0, params: dict[str, Any] | None = None) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).scalar() or default
                except Exception as exc:
                    logger.warning(f"Phase36 metric scalar fallback: {exc}")
                    return default

            async def safe_fetchone(sql: str, params: dict[str, Any] | None = None) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).fetchone()
                except Exception as exc:
                    logger.warning(f"Phase36 metric row fallback: {exc}")
                    return None

            async def safe_fetchall(sql: str, params: dict[str, Any] | None = None) -> list[Any]:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql), params or {})).fetchall()
                except Exception as exc:
                    logger.warning(f"Phase36 metric set fallback: {exc}")
                    return []

            metrics["dominant_organisms"] = int(await safe_scalar(
                "SELECT COALESCE(COUNT(*), 0) FROM strategies WHERE lifecycle_state = 'dominant'",
                0,
            ))

            specialization_rows = await safe_fetchall("""
                SELECT primary_affinity,
                       COALESCE(AVG((bull_survivability + bear_survivability + ranging_survivability) / 3.0), 0) AS survivability,
                       COALESCE(AVG(profile_confidence), 0) AS profile_confidence,
                       COUNT(*) AS n_obs
                FROM organism_regime_profile
                WHERE profiled_at > NOW() - INTERVAL '14 days'
                GROUP BY primary_affinity
                ORDER BY survivability DESC, profile_confidence DESC, n_obs DESC
                LIMIT 20
            """)
            metrics["specialization_rankings"] = [
                {
                    "regime": str(r[0] or "unknown"),
                    "survivability": float(r[1] or 0),
                    "profile_confidence": float(r[2] or 0),
                    "n_obs": int(r[3] or 0),
                }
                for r in specialization_rows
            ]

            scout_rows = await safe_fetchall("""
                SELECT source_scout,
                       COALESCE(AVG(pnl_contribution), 0) AS avg_pnl_contribution,
                       COALESCE(AVG(sharpe_contribution), 0) AS avg_sharpe_contribution,
                       COALESCE(AVG(drawdown_contribution), 0) AS avg_drawdown_contribution,
                       COALESCE(AVG(win_rate_contribution), 0) AS avg_win_rate_contribution,
                       COALESCE(AVG(attribution_weight), 0) AS avg_attribution_weight,
                       COALESCE(SUM(CASE WHEN survived_validation THEN 1 ELSE 0 END), 0) AS n_survived,
                       COUNT(*) AS n_obs
                FROM scout_economic_attribution
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY source_scout
                ORDER BY avg_pnl_contribution DESC, avg_sharpe_contribution DESC
                LIMIT 20
            """)
            metrics["scout_rankings"] = [
                {
                    "scout": str(r[0] or "unknown"),
                    "avg_pnl_contribution": float(r[1] or 0),
                    "avg_sharpe_contribution": float(r[2] or 0),
                    "avg_drawdown_contribution": float(r[3] or 0),
                    "avg_win_rate_contribution": float(r[4] or 0),
                    "avg_attribution_weight": float(r[5] or 0),
                    "n_survived": int(r[6] or 0),
                    "n_obs": int(r[7] or 0),
                }
                for r in scout_rows
            ]

            copy_rows = await safe_fetchall("""
                SELECT leader_id, follower_id,
                       COALESCE(AVG(sync_quality_score), 0) AS sync_quality_score,
                       COALESCE(AVG(replay_integrity), 0) AS replay_integrity,
                       COALESCE(AVG(follower_survivability), 0) AS follower_survivability,
                       COUNT(*) AS n_obs
                FROM copy_quality_metrics
                WHERE measured_at > NOW() - INTERVAL '14 days'
                GROUP BY leader_id, follower_id
                ORDER BY sync_quality_score DESC, replay_integrity DESC
                LIMIT 20
            """)
            metrics["copy_quality_rankings"] = [
                {
                    "leader_id": str(r[0] or "unknown"),
                    "follower_id": str(r[1] or "unknown"),
                    "sync_quality_score": float(r[2] or 0),
                    "replay_integrity": float(r[3] or 0),
                    "follower_survivability": float(r[4] or 0),
                    "n_obs": int(r[5] or 0),
                }
                for r in copy_rows
            ]

            validation_row = await safe_fetchone("""
                SELECT
                    COALESCE(AVG(composite_fitness_score), 0) AS avg_composite_fitness,
                    COALESCE(AVG(sharpe), 0) AS avg_sharpe,
                    COALESCE(AVG(win_rate), 0) AS avg_win_rate,
                    COALESCE(AVG(total_trades), 0) AS avg_trades,
                    COUNT(*) AS n_backtests
                FROM backtest_results
                WHERE created_at > NOW() - INTERVAL '14 days'
            """)
            if validation_row:
                metrics["validation_snapshot"] = {
                    "avg_composite_fitness": float(validation_row[0] or 0),
                    "avg_sharpe": float(validation_row[1] or 0),
                    "avg_win_rate": float(validation_row[2] or 0),
                    "avg_trades": float(validation_row[3] or 0),
                    "n_backtests": int(validation_row[4] or 0),
                }

            observability_row = await safe_fetchone("""
                SELECT
                    COALESCE(COUNT(*), 0) AS n_retirements,
                    COALESCE(SUM(n_retired), 0) AS total_retired,
                    COALESCE(SUM(n_retirement_pending), 0) AS total_pending
                FROM strategy_retirement
                WHERE analyzed_at > NOW() - INTERVAL '14 days'
            """)
            if observability_row:
                metrics["observability_snapshot"] = {
                    "n_retirement_reports": int(observability_row[0] or 0),
                    "total_retired": int(observability_row[1] or 0),
                    "total_pending": int(observability_row[2] or 0),
                }

            economic_row = await safe_fetchone("""
                SELECT
                    COALESCE(COUNT(*), 0) AS n_attributions,
                    COALESCE(SUM(pnl_contribution), 0) AS total_pnl_contribution,
                    COALESCE(AVG(sharpe_contribution), 0) AS avg_sharpe_contribution,
                    COALESCE(AVG(attribution_weight), 0) AS avg_attribution_weight
                FROM scout_economic_attribution
                WHERE created_at > NOW() - INTERVAL '14 days'
            """)
            if economic_row:
                metrics["economic_circulation_snapshot"] = {
                    "n_attributions": int(economic_row[0] or 0),
                    "total_pnl_contribution": float(economic_row[1] or 0),
                    "avg_sharpe_contribution": float(economic_row[2] or 0),
                    "avg_attribution_weight": float(economic_row[3] or 0),
                }

            drift_row = await safe_fetchone("""
                SELECT
                    COALESCE(composite_severity, 0) AS composite_severity,
                    COALESCE(feature_drift_score, 0) AS feature_drift_score,
                    COALESCE(strategy_drift_score, 0) AS strategy_drift_score,
                    COALESCE(regime_drift_score, 0) AS regime_drift_score,
                    COALESCE(execution_drift_score, 0) AS execution_drift_score
                FROM drift_detection
                ORDER BY detected_at DESC
                LIMIT 1
            """)
            if drift_row:
                metrics["drift_snapshot"] = {
                    "composite_severity": float(drift_row[0] or 0),
                    "feature_drift_score": float(drift_row[1] or 0),
                    "strategy_drift_score": float(drift_row[2] or 0),
                    "regime_drift_score": float(drift_row[3] or 0),
                    "execution_drift_score": float(drift_row[4] or 0),
                }

            retirement_row = await safe_fetchone("""
                SELECT
                    COALESCE(n_strategies_analyzed, 0) AS n_strategies_analyzed,
                    COALESCE(n_active, 0) AS n_active,
                    COALESCE(n_monitor, 0) AS n_monitor,
                    COALESCE(n_retirement_pending, 0) AS n_retirement_pending,
                    COALESCE(n_retired, 0) AS n_retired
                FROM strategy_retirement
                ORDER BY analyzed_at DESC
                LIMIT 1
            """)
            if retirement_row:
                metrics["retirement_snapshot"] = {
                    "n_strategies_analyzed": int(retirement_row[0] or 0),
                    "n_active": int(retirement_row[1] or 0),
                    "n_monitor": int(retirement_row[2] or 0),
                    "n_retirement_pending": int(retirement_row[3] or 0),
                    "n_retired": int(retirement_row[4] or 0),
                }

            exec_row = await safe_fetchone("""
                SELECT
                    COALESCE(execution_degradation_score, 0),
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

        self._compute_composites(metrics)
        await self._persist(metrics)
        await self._update_domain_weights(metrics)
        self.metrics_history.append(metrics)
        return metrics

    def _compute_composites(self, metrics: dict[str, Any]) -> None:
        validation = metrics.get("validation_snapshot", {})
        drift = metrics.get("drift_snapshot", {})
        retirement = metrics.get("retirement_snapshot", {})
        economic = metrics.get("economic_circulation_snapshot", {})
        exec_realism = metrics.get("execution_realism_snapshot", {})

        avg_sharpe = float(validation.get("avg_sharpe", 0.0))
        avg_win_rate = float(validation.get("avg_win_rate", 0.0))
        avg_trades = float(validation.get("avg_trades", 0.0))
        avg_composite = float(validation.get("avg_composite_fitness", 0.0))

        regime_strength = 0.0
        if metrics.get("specialization_rankings"):
            top_regimes = metrics["specialization_rankings"][:3]
            regime_strength = sum(float(x.get("survivability", 0)) for x in top_regimes) / max(1, len(top_regimes))

        scout_signal = 0.0
        if metrics.get("scout_rankings"):
            top_scouts = metrics["scout_rankings"][:5]
            scout_signal = sum(
                max(0.0, float(x.get("avg_pnl_contribution", 0)))
                + max(0.0, float(x.get("avg_sharpe_contribution", 0)))
                + max(0.0, float(x.get("avg_win_rate_contribution", 0)))
                - abs(float(x.get("avg_drawdown_contribution", 0)))
                for x in top_scouts
            ) / max(1, len(top_scouts))
            scout_signal = max(0.0, min(1.0, scout_signal / 10.0))

        copy_signal = 0.0
        if metrics.get("copy_quality_rankings"):
            top_copy = metrics["copy_quality_rankings"][:5]
            copy_signal = sum(
                float(x.get("sync_quality_score", 0)) * 0.4
                + float(x.get("replay_integrity", 0)) * 0.35
                + float(x.get("follower_survivability", 0)) * 0.25
                for x in top_copy
            ) / max(1, len(top_copy))
            copy_signal = max(0.0, min(1.0, copy_signal))

        validation_score = max(0.0, min(1.0,
            0.35 * min(1.0, max(avg_composite, 0.0) / 100.0)
            + 0.20 * min(1.0, max(avg_sharpe, 0.0) / 5.0)
            + 0.20 * max(0.0, min(1.0, avg_win_rate))
            + 0.25 * min(1.0, avg_trades / 20.0)
        ))

        execution_realism_score = max(0.0, min(1.0, 1.0 - float(exec_realism.get("execution_degradation_score", 0.0))))
        drift_penalty = max(0.0, 1.0 - float(drift.get("composite_severity", 0.0)))
        economic_circulation_score = max(0.0, min(1.0,
            0.45 * min(1.0, float(economic.get("n_attributions", 0)) / 50.0)
            + 0.30 * min(1.0, abs(float(economic.get("total_pnl_contribution", 0.0))) / 100.0)
            + 0.25 * min(1.0, max(0.0, float(economic.get("avg_sharpe_contribution", 0.0))) / 2.0)
        ))
        observability_score = max(0.0, min(1.0,
            0.20 * min(1.0, float(metrics["dominant_organisms"]) / 5.0)
            + 0.20 * min(1.0, float(metrics.get("retirement_snapshot", {}).get("n_strategies_analyzed", 0)) / 20.0)
            + 0.20 * min(1.0, float(metrics.get("observability_snapshot", {}).get("n_retirement_reports", 0)) / 10.0)
            + 0.20 * min(1.0, float(len(metrics.get("specialization_rankings", []))) / 10.0)
            + 0.20 * min(1.0, float(len(metrics.get("scout_rankings", []))) / 10.0)
        ))
        specialization_score = max(0.0, min(1.0,
            0.55 * min(1.0, regime_strength / 2.0)
            + 0.25 * min(1.0, scout_signal)
            + 0.20 * min(1.0, float(metrics["dominant_organisms"]) / 3.0)
        ))

        execution_activation_score = max(0.0, min(1.0,
            0.25 * validation_score
            + 0.20 * execution_realism_score
            + 0.20 * specialization_score
            + 0.20 * economic_circulation_score
            + 0.15 * copy_signal
        ))

        full_activation_score = max(0.0, min(1.0,
            0.16 * execution_activation_score
            + 0.16 * execution_realism_score
            + 0.16 * validation_score
            + 0.16 * specialization_score
            + 0.12 * observability_score
            + 0.12 * economic_circulation_score
            + 0.12 * copy_signal * drift_penalty
        ))

        metrics["execution_activation_score"] = round(execution_activation_score, 4)
        metrics["execution_realism_score"] = round(execution_realism_score, 4)
        metrics["scout_ecosystem_score"] = round(max(0.0, min(1.0, 0.55 * scout_signal + 0.45 * economic_circulation_score)), 4)
        metrics["advanced_validation_score"] = round(validation_score, 4)
        metrics["specialization_score"] = round(specialization_score, 4)
        metrics["observability_score"] = round(observability_score, 4)
        metrics["economic_circulation_score"] = round(economic_circulation_score, 4)
        metrics["full_activation_score"] = round(full_activation_score, 4)

    async def _persist(self, metrics: dict[str, Any]) -> None:
        payload = {
            **metrics,
            "specialization_rankings": json.dumps(metrics["specialization_rankings"]),
            "scout_rankings": json.dumps(metrics["scout_rankings"]),
            "copy_quality_rankings": json.dumps(metrics["copy_quality_rankings"]),
            "validation_snapshot": json.dumps(metrics["validation_snapshot"]),
            "observability_snapshot": json.dumps(metrics["observability_snapshot"]),
            "economic_circulation_snapshot": json.dumps(metrics["economic_circulation_snapshot"]),
            "drift_snapshot": json.dumps(metrics["drift_snapshot"]),
            "retirement_snapshot": json.dumps(metrics["retirement_snapshot"]),
            "metadata": json.dumps({"collected_at": datetime.now(timezone.utc).isoformat()}),
        }
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase36_full_ecosystem_metrics (
                    recorded_at, runtime_minutes,
                    execution_activation_score, execution_realism_score,
                    scout_ecosystem_score, advanced_validation_score,
                    specialization_score, observability_score,
                    economic_circulation_score, full_activation_score,
                    dominant_organisms, specialization_rankings, scout_rankings,
                    copy_quality_rankings, validation_snapshot,
                    observability_snapshot, economic_circulation_snapshot,
                    drift_snapshot, retirement_snapshot,
                    metadata
                ) VALUES (
                    :recorded_at, :runtime_minutes,
                    :execution_activation_score, :execution_realism_score,
                    :scout_ecosystem_score, :advanced_validation_score,
                    :specialization_score, :observability_score,
                    :economic_circulation_score, :full_activation_score,
                    :dominant_organisms, CAST(:specialization_rankings AS jsonb), CAST(:scout_rankings AS jsonb),
                    CAST(:copy_quality_rankings AS jsonb), CAST(:validation_snapshot AS jsonb),
                    CAST(:observability_snapshot AS jsonb), CAST(:economic_circulation_snapshot AS jsonb),
                    CAST(:drift_snapshot AS jsonb), CAST(:retirement_snapshot AS jsonb),
                    CAST(:metadata AS jsonb)
                )
            """), payload)

    async def _update_domain_weights(self, metrics: dict[str, Any]) -> None:
        weights = {
            "execution": metrics.get("execution_activation_score", 0.0),
            "realism": metrics.get("execution_realism_score", 0.0),
            "scout": metrics.get("scout_ecosystem_score", 0.0),
            "validation": metrics.get("advanced_validation_score", 0.0),
            "specialization": metrics.get("specialization_score", 0.0),
            "observability": metrics.get("observability_score", 0.0),
            "circulation": metrics.get("economic_circulation_score", 0.0),
        }
        total = sum(max(0.0, float(v)) for v in weights.values())
        if total <= 0:
            normalized = {k: 1.0 / len(weights) for k in weights}
        else:
            normalized = {k: max(0.0, float(v)) / total for k, v in weights.items()}

        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase36_activation_weights (domain_weights, metadata)
                VALUES (CAST(:weights AS jsonb), CAST(:metadata AS jsonb))
            """), {
                "weights": json.dumps(normalized),
                "metadata": json.dumps({"source": "phase36_full_ecosystem_activation"}),
            })

    async def close(self) -> None:
        await self.engine.dispose()


class Phase36FullEcosystemController:
    def __init__(
        self,
        duration_minutes: int = 720,
        metrics_interval: int = 300,
        heartbeat_interval: int = 60,
        ideation_per_cycle: int = 2,
        queue_batch_size: int = 25,
    ):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = metrics_interval
        self.heartbeat_interval = heartbeat_interval
        self.ideation_per_cycle = max(1, ideation_per_cycle)
        self.queue_batch_size = max(1, queue_batch_size)
        self.db_url = settings.database_url
        self.metrics = Phase36MetricsCollector(self.db_url)
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

        self._runtime_db: Optional[TimescaleClient] = None
        self._redis_client: Optional[Redis] = None
        self._ideators: list[IdeatorAgentV2] = []
        self._coder_agent: Optional[CoderAgent] = None
        self._backtest_runner: Optional[BacktestRunner] = None
        self._validator_agent: Optional[ValidatorAgent] = None
        self._circulation_cycle: int = 0
        self._runtime_baseline: Optional[dict[str, int]] = None
        self._runtime_activity: dict[str, int] = {
            "strategies": 0,
            "backtests": 0,
            "trades": 0,
            "mutations": 0,
            "retired": 0,
            "promoted": 0,
        }

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

        # Provide governance execution context to engines (best-effort).
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
                pass

        self._runtime_db = TimescaleClient(self.db_url)
        await self._runtime_db.connect()

        try:
            self._redis_client = Redis.from_url(settings.redis_url)
        except Exception as exc:
            self._redis_client = None
            logger.warning(f"Phase 36 Redis unavailable for circulation agents: {exc}")

        if self._redis_client is not None:
            self._ideators = [
                IdeatorAgentV2(0, 0.5, self._redis_client, self._runtime_db, mode="lean"),
                IdeatorAgentV2(4, 0.0, self._redis_client, self._runtime_db, mode="local"),
            ]
            self._coder_agent = CoderAgent(self._redis_client, self._runtime_db)
            self._backtest_runner = BacktestRunner(self._redis_client)
            self._validator_agent = ValidatorAgent(self._redis_client, self._runtime_db)

            try:
                await self._backtest_runner.timescale.connect()
            except Exception as exc:
                logger.warning(f"Phase 36 BacktestRunner Timescale init failed: {exc}")

            for ideator in self._ideators:
                try:
                    ideator._ctx_cache = await ideator._build_context()
                    ideator._ctx_cycle = 0
                except Exception as exc:
                    logger.warning(f"{ideator.name}: context preload failed: {exc}")
        else:
            logger.warning("Phase 36 circulation layer disabled: Redis client not available")

        self._engines_initialized = True
        logger.info("Phase 36 engines initialized")

    async def _capture_runtime_snapshot(self) -> dict[str, int]:
        if self._runtime_db is None:
            return {
                "strategies": 0,
                "backtests": 0,
                "trades": 0,
                "mutations": 0,
                "retired": 0,
                "promoted": 0,
            }

        try:
            async with self._runtime_db.engine.connect() as conn:
                row = (
                    await conn.execute(
                        sa_text(
                            """
                            SELECT
                                (SELECT COUNT(*) FROM strategies) AS strategies,
                                (SELECT COUNT(*) FROM backtest_results) AS backtests,
                                (SELECT COALESCE(SUM(total_trades), 0) FROM backtest_results) AS trades,
                                (SELECT COUNT(*) FROM mutation_memory) AS mutations,
                                (SELECT COUNT(*) FROM strategies WHERE lifecycle_state = 'retired') AS retired,
                                (SELECT COUNT(*) FROM strategies WHERE lifecycle_state = 'dominant') AS promoted
                            """
                        )
                    )
                ).fetchone()
            if not row:
                return {
                    "strategies": 0,
                    "backtests": 0,
                    "trades": 0,
                    "mutations": 0,
                    "retired": 0,
                    "promoted": 0,
                }

            return {
                "strategies": int(row[0] or 0),
                "backtests": int(row[1] or 0),
                "trades": int(row[2] or 0),
                "mutations": int(row[3] or 0),
                "retired": int(row[4] or 0),
                "promoted": int(row[5] or 0),
            }
        except Exception as exc:
            logger.warning(f"Phase 36 runtime snapshot failed: {exc}")
            return {
                "strategies": 0,
                "backtests": 0,
                "trades": 0,
                "mutations": 0,
                "retired": 0,
                "promoted": 0,
            }

    async def _run_single_ideation(self, ideator: IdeatorAgentV2, cycle: int) -> int:
        if self._runtime_db is None:
            return 0

        try:
            if cycle % 10 == 0 or not getattr(ideator, "_ctx_cache", None):
                ideator._ctx_cache = await ideator._build_context()
            ideator._ctx_cycle = cycle

            spec, prompt, raw = await ideator._generate(ideator._ctx_cache)
            if not spec:
                return 0

            sig = compute_strategy_signature(spec)
            existing = await self._runtime_db.get_strategy_signatures(limit=2000)
            if sig in existing:
                return 0

            await self._runtime_db.save_strategy(
                spec,
                status="pending_code",
                author_agent=ideator.name,
                prompt=prompt,
                raw_response=raw,
                strategy_signature=sig,
            )
            return 1
        except Exception as exc:
            logger.warning(f"{ideator.name}: ideation cycle failed: {exc}")
            return 0

    async def _run_production_circulation(self) -> None:
        if self._runtime_db is None or not self._ideators or self._coder_agent is None:
            return

        self._circulation_cycle += 1
        before = await self._capture_runtime_snapshot()

        generated = 0
        coded = 0
        backtested = 0
        validated = 0

        for ideator in self._ideators[: self.ideation_per_cycle]:
            generated += await self._run_single_ideation(ideator, self._circulation_cycle)

        pending_code = await self._runtime_db.get_strategies_by_status("pending_code")
        for strategy in pending_code[: self.queue_batch_size]:
            await self._coder_agent._code_strategy(strategy)
            coded += 1

        if self._backtest_runner is not None:
            pending_backtest = await self._backtest_runner.timescale.get_strategies_by_status("pending_backtest")
            for strategy in pending_backtest[: self.queue_batch_size]:
                await self._backtest_runner.process_strategy(strategy)
                backtested += 1

        if self._validator_agent is not None:
            pending_validation = await self._runtime_db.get_strategies_by_status("pending_validation")
            for strategy in pending_validation[: self.queue_batch_size]:
                await self._validator_agent._validate_one(strategy["id"], strategy.get("name", "unknown"))
                validated += 1

        after = await self._capture_runtime_snapshot()

        if self._runtime_baseline is None:
            self._runtime_baseline = before

        self._runtime_activity = {
            "strategies": max(0, int(after["strategies"] - self._runtime_baseline["strategies"])),
            "backtests": max(0, int(after["backtests"] - self._runtime_baseline["backtests"])),
            "trades": max(0, int(after["trades"] - self._runtime_baseline["trades"])),
            "mutations": max(0, int(after["mutations"] - self._runtime_baseline["mutations"])),
            "retired": max(0, int(after["retired"] - self._runtime_baseline["retired"])),
            "promoted": max(0, int(after["promoted"] - self._runtime_baseline["promoted"])),
        }

        logger.info(
            "[Circulation] "
            f"generated={generated} coded={coded} backtested={backtested} validated={validated} "
            f"live_strategies={self._runtime_activity['strategies']} "
            f"live_backtests={self._runtime_activity['backtests']}"
        )

    async def _safe_call(self, name: str, coro, timeout: int = 60) -> None:
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.debug(f"Phase36[{name}] OK")
        except asyncio.TimeoutError:
            logger.warning(f"Phase36[{name}] TIMEOUT after {timeout}s")
        except Exception as e:
            logger.warning(f"Phase36[{name}] FAILED: {type(e).__name__}: {e}")

    async def _run_phase36_cycle(self) -> None:
        await self._ensure_engines()

        await self._safe_call("ProductionCirculation", self._run_production_circulation(), timeout=240)

        await self._safe_call("DominantOrganism", self._dominant_tracker._tracking_cycle())
        await self._safe_call("MutationLineage", self._lineage_tracker._lineage_cycle())
        await self._safe_call("RegimeSpecialization", self._regime_engine._profiling_cycle())
        await self._safe_call("ScoutDivergence", self._scout_engine._divergence_cycle())
        await self._safe_call("PortfolioEvolution", self._portfolio_engine._pressure_cycle())
        await self._safe_call("RegimeStress", self._stress_engine._stress_cycle())
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
        logger.info("PHASE 36 - FULL ECOSYSTEM ACTIVATION SOAK STARTING")
        logger.info(
            f"Duration: {self.duration_minutes}m | Metrics interval: {self.metrics_interval}s | "
            f"Heartbeat interval: {self.heartbeat_interval}s | "
            f"Ideation per cycle: {self.ideation_per_cycle} | Queue batch size: {self.queue_batch_size}"
        )
        logger.info("=" * 72)

        schema_probe = TimescaleClient(self.db_url)
        await schema_probe.connect()
        await self._ensure_schema_compatibility(schema_probe)
        await schema_probe.validate_schema_contracts(strict=True)
        await schema_probe.close()

        await self.metrics.initialize()

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
                await self._run_phase36_cycle()
                metrics = await self.metrics.collect(elapsed_minutes)
                self._print_status(metrics, elapsed, remaining)

                sleep_remaining = min(self.metrics_interval, remaining)
                while sleep_remaining > 0 and not self._shutdown:
                    sleep_step = min(self.heartbeat_interval, sleep_remaining)
                    await asyncio.sleep(sleep_step)
                    sleep_remaining -= sleep_step

                    if sleep_remaining > 0 and not self._shutdown:
                        heartbeat_elapsed = time.time() - self._start_time
                        heartbeat_remaining = self.duration_seconds - heartbeat_elapsed
                        self._print_heartbeat(metrics, heartbeat_elapsed, heartbeat_remaining)
        finally:
            await self._finalize()

    def _request_shutdown(self) -> None:
        self._shutdown = True

    def _print_status(self, metrics: dict[str, Any], elapsed: float, remaining: float) -> None:
        e = int(elapsed / 60)
        r = int(remaining / 60)
        print(f"\n[Phase36] T+{e}m / T-{r}m")
        print(
            "  Scores: "
            f"EA={metrics.get('execution_activation_score', 0):.3f} "
            f"ER={metrics.get('execution_realism_score', 0):.3f} "
            f"SC={metrics.get('scout_ecosystem_score', 0):.3f} "
            f"AV={metrics.get('advanced_validation_score', 0):.3f} "
            f"SP={metrics.get('specialization_score', 0):.3f} "
            f"OB={metrics.get('observability_score', 0):.3f} "
            f"EC={metrics.get('economic_circulation_score', 0):.3f} "
            f"FA={metrics.get('full_activation_score', 0):.3f}"
        )
        print(
            "  Core: "
            f"dominant={metrics.get('dominant_organisms', 0)} "
            f"scouts={len(metrics.get('scout_rankings', []))} "
            f"specialists={len(metrics.get('specialization_rankings', []))} "
            f"copy_pairs={len(metrics.get('copy_quality_rankings', []))}"
        )
        sys.stdout.flush()

    def _print_heartbeat(self, metrics: dict[str, Any], elapsed: float, remaining: float) -> None:
        runtime_minutes = int(elapsed / 60)
        strategies = int(self._runtime_activity.get("strategies", 0))
        backtests = int(self._runtime_activity.get("backtests", 0))
        trades = int(self._runtime_activity.get("trades", 0))
        mutations = int(self._runtime_activity.get("mutations", 0))
        retired = int(self._runtime_activity.get("retired", 0))
        promoted = int(self._runtime_activity.get("promoted", 0))

        if strategies == 0 and backtests == 0 and trades == 0:
            # Fallback to historical aggregates only when runtime circulation has not produced deltas yet.
            strategies = int(metrics.get("dominant_organisms", 0))
            backtests = int(metrics.get("validation_snapshot", {}).get("n_backtests", 0))
            trades = int(metrics.get("validation_snapshot", {}).get("avg_trades", 0))

        logger.info(
            f"[Heartbeat] runtime={runtime_minutes}m "
            f"strategies={strategies} "
            f"backtests={backtests} "
            f"trades={trades} "
            f"mutations={mutations} "
            f"retired={retired} "
            f"promoted={promoted}"
        )

        print(f"[Phase36] heartbeat T+{runtime_minutes}m / T-{int(remaining / 60)}m")
        sys.stdout.flush()

    async def _finalize(self) -> None:
        total_minutes = int((time.time() - self._start_time) / 60) if self._start_time else 0
        logger.info(f"Phase 36 soak complete after {total_minutes} minutes")

        latest = self.metrics.metrics_history[-1] if self.metrics.metrics_history else {}
        initial = self.metrics.metrics_history[0] if self.metrics.metrics_history else {}

        await self._generate_reports(initial, latest, total_minutes)
        await self.metrics.close()

        if self._backtest_runner is not None:
            try:
                await self._backtest_runner.timescale.close()
            except Exception as exc:
                logger.warning(f"BacktestRunner close failed: {exc}")

        if self._runtime_db is not None:
            try:
                await self._runtime_db.close()
            except Exception as exc:
                logger.warning(f"Runtime DB close failed: {exc}")

        if self._redis_client is not None:
            try:
                await self._redis_client.aclose()
            except Exception as exc:
                logger.warning(f"Redis close failed: {exc}")

    async def _generate_reports(self, initial: dict[str, Any], latest: dict[str, Any], duration_minutes: int) -> None:
        def pct_delta(key: str) -> float:
            a = float(initial.get(key, 0) or 0)
            b = float(latest.get(key, 0) or 0)
            if a == 0:
                return b
            return (b - a) / abs(a)

        execution_lines = [
            "# PHASE36_EXECUTION_ACTIVATION_REPORT",
            "",
            f"Duration minutes: {duration_minutes}",
            f"Execution activation score: {latest.get('execution_activation_score', 0)}",
            f"Full activation score: {latest.get('full_activation_score', 0)}",
            f"Dominant organisms: {latest.get('dominant_organisms', 0)}",
            f"Specialization rankings: {json.dumps(latest.get('specialization_rankings', [])[:10], indent=2)}",
        ]

        realism_lines = [
            "# PHASE36_EXECUTION_REALISM_REPORT",
            "",
            f"Execution realism score: {latest.get('execution_realism_score', 0)}",
            f"Copy quality rankings: {json.dumps(latest.get('copy_quality_rankings', [])[:10], indent=2)}",
            f"Drift snapshot: {json.dumps(latest.get('drift_snapshot', {}), indent=2)}",
        ]

        scout_lines = [
            "# PHASE36_SCOUT_ECOSYSTEM_REPORT",
            "",
            f"Scout ecosystem score: {latest.get('scout_ecosystem_score', 0)}",
            f"Scout rankings: {json.dumps(latest.get('scout_rankings', [])[:15], indent=2)}",
            f"Economic circulation: {json.dumps(latest.get('economic_circulation_snapshot', {}), indent=2)}",
        ]

        validation_lines = [
            "# PHASE36_ADVANCED_VALIDATION_REPORT",
            "",
            f"Advanced validation score: {latest.get('advanced_validation_score', 0)}",
            f"Validation snapshot: {json.dumps(latest.get('validation_snapshot', {}), indent=2)}",
            f"Retirement snapshot: {json.dumps(latest.get('retirement_snapshot', {}), indent=2)}",
        ]

        specialization_lines = [
            "# PHASE36_SPECIALIZATION_REPORT",
            "",
            f"Specialization score: {latest.get('specialization_score', 0)}",
            f"Specialization rankings: {json.dumps(latest.get('specialization_rankings', [])[:15], indent=2)}",
        ]

        observability_lines = [
            "# PHASE36_OBSERVABILITY_REPORT",
            "",
            f"Observability score: {latest.get('observability_score', 0)}",
            f"Observability snapshot: {json.dumps(latest.get('observability_snapshot', {}), indent=2)}",
            f"Drift snapshot: {json.dumps(latest.get('drift_snapshot', {}), indent=2)}",
        ]

        pass_checks = {
            "activation score present": latest.get("full_activation_score", 0) > 0,
            "execution layer activated": latest.get("execution_activation_score", 0) >= 0.25,
            "execution realism tracked": latest.get("execution_realism_score", 0) >= 0.25,
            "scout ecosystem tracked": len(latest.get("scout_rankings", [])) >= 1,
            "advanced validation tracked": latest.get("advanced_validation_score", 0) >= 0.20,
            "specialization tracked": len(latest.get("specialization_rankings", [])) >= 1,
            "observability tracked": latest.get("observability_score", 0) >= 0.20,
            "economic circulation tracked": latest.get("economic_circulation_score", 0) >= 0.10,
            "activation improves over time": pct_delta("full_activation_score") >= 0,
        }
        passed = all(pass_checks.values())

        cert_lines = [
            "# PHASE36_FULL_ECOSYSTEM_CERTIFICATION",
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
                    "execution_activation_score": latest.get("execution_activation_score", 0),
                    "execution_realism_score": latest.get("execution_realism_score", 0),
                    "scout_ecosystem_score": latest.get("scout_ecosystem_score", 0),
                    "advanced_validation_score": latest.get("advanced_validation_score", 0),
                    "specialization_score": latest.get("specialization_score", 0),
                    "observability_score": latest.get("observability_score", 0),
                    "economic_circulation_score": latest.get("economic_circulation_score", 0),
                    "full_activation_score": latest.get("full_activation_score", 0),
                },
                indent=2,
            ),
        ])

        reports = {
            "PHASE36_EXECUTION_ACTIVATION_REPORT.md": "\n".join(execution_lines) + "\n",
            "PHASE36_EXECUTION_REALISM_REPORT.md": "\n".join(realism_lines) + "\n",
            "PHASE36_SCOUT_ECOSYSTEM_REPORT.md": "\n".join(scout_lines) + "\n",
            "PHASE36_ADVANCED_VALIDATION_REPORT.md": "\n".join(validation_lines) + "\n",
            "PHASE36_SPECIALIZATION_REPORT.md": "\n".join(specialization_lines) + "\n",
            "PHASE36_OBSERVABILITY_REPORT.md": "\n".join(observability_lines) + "\n",
            "PHASE36_FULL_ECOSYSTEM_CERTIFICATION.md": "\n".join(cert_lines) + "\n",
        }

        for name, content in reports.items():
            (ROOT / name).write_text(content, encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 36 full ecosystem activation soak")
    parser.add_argument("--duration-minutes", type=int, default=720)
    parser.add_argument("--metrics-interval", type=int, default=300)
    parser.add_argument("--heartbeat-interval", type=int, default=60)
    parser.add_argument("--ideation-per-cycle", type=int, default=2)
    parser.add_argument("--queue-batch-size", type=int, default=25)
    args = parser.parse_args()

    controller = Phase36FullEcosystemController(
        duration_minutes=args.duration_minutes,
        metrics_interval=args.metrics_interval,
        heartbeat_interval=args.heartbeat_interval,
        ideation_per_cycle=args.ideation_per_cycle,
        queue_batch_size=args.queue_batch_size,
    )
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
