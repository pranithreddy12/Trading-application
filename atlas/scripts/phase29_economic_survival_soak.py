"""
phase29_economic_survival_soak.py — Phase 29: 12-Hour Economic Evolution Soak

This script runs the complete ATLAS autonomous cycle with ALL Phase 29 features
enabled and captures economic efficiency metrics every 30 minutes.

Usage:
    python scripts/phase29_economic_survival_soak.py
    python scripts/phase29_economic_survival_soak.py --duration-minutes 720

EVERY 30 MINUTES: captures economic quality, evolution, scouts, portfolio, operations.
GENERATES: 8 Phase 29 reports on completion.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.sql import text

# ── Path Setup ────────────────────────────────────────────────────────────────
# Must happen before atlas.* imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)       # atlas/
_WORKSPACE_ROOT = os.path.dirname(_PROJECT_ROOT)    # parent of atlas/
sys.path.insert(0, _WORKSPACE_ROOT)
sys.path.insert(0, _PROJECT_ROOT)
os.environ["PYTHONPATH"] = f"{_WORKSPACE_ROOT}{os.pathsep}{_PROJECT_ROOT}"

from atlas.agents.l2_strategy.coder_agent import CoderAgent
from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2
from atlas.agents.l2_strategy.mutator_agent import MutatorAgent
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent
from atlas.agents.l4_risk.risk_controller import RiskController
from atlas.agents.l5_execution.broker_adapter import SimulatorAdapter
from atlas.agents.l7_meta.mutation_pattern_agent import MutationPatternAgent
from atlas.agents.l5_execution.execution_gateway import ExecutionGateway
from atlas.agents.scouts.regime_scout import RegimeScout
from atlas.agents.scouts.liquidity_scout import LiquidityScout
from atlas.agents.scouts.correlation_scout import CorrelationScout
from atlas.agents.scouts.execution_scout import ExecutionScout
from atlas.agents.l3_validation.walk_forward_analyzer import WalkForwardAnalyzer
from atlas.agents.l3_validation.monte_carlo_simulator import MonteCarloSimulator
from atlas.agents.l3_validation.overfitting_detector import OverfittingDetector
from atlas.agents.l3_validation.regime_validator import RegimeValidator
from atlas.agents.l3_validation.cost_stress_tester import CostStressTester
from atlas.agents.l1_pattern.pattern_recognition_engine import PatternRecognitionEngine
from atlas.agents.l7_meta.feature_importance_engine import FeatureImportanceEngine
from atlas.agents.l7_meta.drift_detection_engine import DriftDetectionEngine
from atlas.agents.l7_meta.strategy_retirement_engine import StrategyRetirementEngine
from atlas.agents.l6_portfolio.portfolio_intelligence_engine import PortfolioIntelligenceEngine
from atlas.agents.l6_portfolio.capital_allocator import CapitalAllocator
from atlas.agents.l6_portfolio.ensemble_execution_engine import EnsembleExecutionEngine
from atlas.agents.l6_portfolio.advanced_portfolio_optimizer import AdvancedPortfolioOptimizer
from atlas.agents.l5_execution.execution_realism_engine import ExecutionRealismEngine
from atlas.agents.l4_risk.systemic_risk_engine import SystemicRiskEngine
from atlas.agents.l4_risk.stress_test_engine import StressTestEngine
from atlas.agents.l4_risk.capital_preservation_engine import CapitalPreservationEngine
from atlas.agents.l7_meta.replay_engine import ReplayEngine
from atlas.agents.l7_meta.system_health_engine import SystemHealthEngine
from atlas.agents.l7_meta.deployment_governor import DeploymentGovernor
from atlas.agents.l7_meta.prompt_evolution_engine import PromptEvolutionEngine
from atlas.agents.l7_meta.mutation_policy_engine import MutationPolicyEngine
from atlas.agents.l7_meta.feature_evolution_engine import FeatureEvolutionEngine
from atlas.agents.l7_meta.agent_performance_governor import AgentPerformanceGovernor
from atlas.agents.scouts.news_intelligence_engine import NewsIntelligenceEngine
from atlas.agents.scouts.source_reliability_engine import SourceReliabilityEngine
from atlas.agents.scouts.hypothesis_validation_engine import HypothesisValidationEngine
from atlas.agents.l7_meta.scout_synthesis_engine import ScoutSynthesisEngine
from atlas.agents.l7_meta.anti_poisoning_engine import AntiPoisoningEngine
from atlas.agents.l7_meta.economic_attribution_engine import EconomicAttributionEngine
from atlas.agents.l7_meta.economic_efficiency_engine import EconomicEfficiencyEngine
from atlas.agents.l7_meta.entropy_governance_engine import EntropyGovernanceEngine
from atlas.config.settings import get_settings
from atlas.core.event_lineage import EventLineageClient
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.scripts.soak.phase24_monitor import SoakMonitor


# ── Report Directory ──────────────────────────────────────────────────────────
REPORT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent

# ── Checkpoint Snapshots ──────────────────────────────────────────────────────
CHECKPOINT_INTERVAL = 1800  # Every 30 minutes


def _build_agents(redis_client: Redis, db_client: TimescaleClient) -> list:
    broker = SimulatorAdapter(default_price=100.0, fill_latency_ms=10)
    risk = RiskController(redis_client, db_client)
    lineage = EventLineageClient(db_client)

    return [
        # Phase 10: Internal Scout Network
        RegimeScout(redis_client, db_client),
        LiquidityScout(redis_client, db_client),
        CorrelationScout(redis_client, db_client),
        ExecutionScout(redis_client, db_client),
        # Phase 11: Advanced Validation & Pattern Intelligence
        WalkForwardAnalyzer(redis_client, db_client),
        MonteCarloSimulator(redis_client, db_client),
        OverfittingDetector(redis_client, db_client),
        RegimeValidator(redis_client, db_client),
        CostStressTester(redis_client, db_client),
        PatternRecognitionEngine(redis_client, db_client),
        FeatureImportanceEngine(redis_client, db_client),
        # Phase 12: Portfolio Intelligence & Capital Realism
        PortfolioIntelligenceEngine(redis_client, db_client),
        CapitalAllocator(redis_client, db_client),
        EnsembleExecutionEngine(redis_client, db_client),
        ExecutionRealismEngine(redis_client, db_client),
        DriftDetectionEngine(redis_client, db_client),
        StrategyRetirementEngine(redis_client, db_client),
        # Phase 13: Production Governance & Reliability
        ReplayEngine(redis_client, db_client),
        SystemHealthEngine(redis_client, db_client),
        DeploymentGovernor(redis_client, db_client),
        # Phase 14: Portfolio Durability & Risk Intelligence
        SystemicRiskEngine(redis_client, db_client),
        StressTestEngine(redis_client, db_client),
        CapitalPreservationEngine(redis_client, db_client),
        AdvancedPortfolioOptimizer(redis_client, db_client),
        # Phase 15: True Meta-Learning
        PromptEvolutionEngine(redis_client, db_client),
        MutationPolicyEngine(redis_client, db_client),
        FeatureEvolutionEngine(redis_client, db_client),
        AgentPerformanceGovernor(redis_client, db_client),
        # Phase 16-26: External Intelligence & Coupling
        NewsIntelligenceEngine(redis_client, db_client),
        SourceReliabilityEngine(redis_client, db_client),
        HypothesisValidationEngine(redis_client, db_client),
        ScoutSynthesisEngine(redis_client, db_client),
        AntiPoisoningEngine(redis_client, db_client),
        EconomicAttributionEngine(redis_client, db_client),
        # PHASE 29: Economic Efficiency Engine
        EconomicEfficiencyEngine(redis_client, db_client),
        EntropyGovernanceEngine(redis_client, db_client),
        # L2-L5: Core pipeline
        IdeatorAgentV2(0, 0.5, redis_client, db_client, mode="rich"),
        CoderAgent(redis_client, db_client),
        MutatorAgent(redis_client, db_client),
        BacktestRunner(redis_client),
        ValidatorAgent(redis_client, db_client),
        ExecutionGateway(redis_client, db_client, broker, risk, lineage),
        MutationPatternAgent(redis_client, db_client),
    ]


async def _start_agents(agents: list) -> list[asyncio.Task]:
    tasks: list[asyncio.Task] = []
    for agent in agents:
        await agent.start()
        if getattr(agent, "_main_task", None):
            tasks.append(agent._main_task)
    return tasks


async def _stop_agents(agents: list) -> None:
    stop_results = await asyncio.gather(
        *(agent.stop() for agent in reversed(agents)),
        return_exceptions=True,
    )
    for agent, result in zip(reversed(agents), stop_results):
        if isinstance(result, Exception):
            logger.warning(f"Agent stop failed — {getattr(agent, 'name', agent)}: {result}")


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT CAPTURE — every 30 minutes
# ══════════════════════════════════════════════════════════════════════════════

async def _capture_checkpoint(db: TimescaleClient, checkpoint_num: int, elapsed_hours: float) -> dict:
    """Capture all economic, evolutionary, and operational metrics for this checkpoint."""
    snapshot = {
        "checkpoint": checkpoint_num,
        "elapsed_hours": round(elapsed_hours, 2),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with db.engine.connect() as conn:
            # ── Economic Quality ────────────────────────────────────────
            r = await conn.execute(text("""
                SELECT
                    COALESCE(AVG(expectancy), 0) as avg_expectancy,
                    COALESCE(AVG(risk_adjusted_return), 0) as avg_risk_return,
                    COALESCE(AVG(return_per_drawdown), 0) as avg_ret_per_dd,
                    COALESCE(AVG(strategy_half_life_hours), 0) as avg_half_life,
                    COALESCE(AVG(mutation_survival_rate), 0) as avg_mutation_survival
                FROM economic_efficiency_analysis
                WHERE analyzed_at > NOW() - INTERVAL '24 hours'
            """))
            row = r.fetchone()
            if row:
                snapshot["economic_quality"] = {
                    "avg_expectancy": float(row[0] or 0),
                    "avg_risk_adjusted_return": float(row[1] or 0),
                    "avg_return_per_drawdown": float(row[2] or 0),
                    "avg_strategy_half_life_hours": float(row[3] or 0),
                    "avg_mutation_survival": float(row[4] or 0),
                }

            # ── Capital Preservation ────────────────────────────────────
            r2 = await conn.execute(text("""
                SELECT drawdown_pct, action_taken, peak_value, current_value
                FROM capital_preservation_state
                ORDER BY checked_at DESC LIMIT 1
            """))
            dd_row = r2.fetchone()
            if dd_row:
                snapshot["capital_preservation"] = {
                    "current_drawdown_pct": float(dd_row[0] or 0),
                    "action_taken": str(dd_row[1] or "none"),
                    "peak_value": float(dd_row[2] or 0),
                    "current_value": float(dd_row[3] or 0),
                }

            # ── Mutation Fitness ────────────────────────────────────────
            r3 = await conn.execute(text("""
                SELECT
                    mutation_type,
                    SUM(total_applications) as total,
                    COALESCE(AVG(survival_rate), 0) as avg_survival
                FROM mutation_survival_log
                GROUP BY mutation_type
                ORDER BY total DESC
                LIMIT 10
            """))
            mutations = []
            for row3 in r3.fetchall():
                mutations.append({
                    "mutation_type": str(row3[0]),
                    "total_applications": int(row3[1] or 0),
                    "avg_survival_rate": float(row3[2] or 0),
                })
            snapshot["mutation_fitness"] = {
                "families": mutations,
                "total_families": len(mutations),
            }

            # ── Scout Predictive Value ──────────────────────────────────
            r4 = await conn.execute(text("""
                SELECT
                    source_scout,
                    COALESCE(AVG(economic_score_penalized), 0) as avg_score,
                    COALESCE(AVG(contradiction_rate), 0) as avg_contra
                FROM scout_predictive_value_log
                WHERE computed_at > NOW() - INTERVAL '24 hours'
                GROUP BY source_scout
                ORDER BY avg_score DESC
                LIMIT 10
            """))
            scouts = []
            for row4 in r4.fetchall():
                scouts.append({
                    "source_scout": str(row4[0]),
                    "avg_economic_score": float(row4[1] or 0),
                    "avg_contradiction_rate": float(row4[2] or 0),
                })
            snapshot["scout_predictive_value"] = {
                "scouts": scouts,
                "predictive_divergence": (
                    max(s["avg_economic_score"] for s in scouts) - min(s["avg_economic_score"] for s in scouts)
                ) if len(scouts) > 1 else 0.0,
            }

            # ── Portfolio Health ────────────────────────────────────────
            r5 = await conn.execute(text("""
                SELECT
                    diversification_score,
                    portfolio_survivability,
                    concentration_risk,
                    correlation_collapse_risk,
                    contagion_exposure,
                    active_strategies
                FROM portfolio_evolution_log
                ORDER BY created_at DESC LIMIT 1
            """))
            port_row = r5.fetchone()
            if port_row:
                snapshot["portfolio_health"] = {
                    "diversification_score": float(port_row[0] or 0),
                    "portfolio_survivability": float(port_row[1] or 0),
                    "concentration_risk": float(port_row[2] or 0),
                    "correlation_collapse_risk": float(port_row[3] or 0),
                    "contagion_exposure": float(port_row[4] or 0),
                    "active_strategies": int(port_row[5] or 0),
                }

            # ── System Health ───────────────────────────────────────────
            r6 = await conn.execute(text("""
                SELECT composite_score, n_degraded, n_total
                FROM system_health
                ORDER BY checked_at DESC LIMIT 1
            """))
            sys_row = r6.fetchone()
            if sys_row:
                snapshot["system_health"] = {
                    "composite_score": float(sys_row[0] or 0),
                    "n_degraded": int(sys_row[1] or 0),
                    "n_total": int(sys_row[2] or 0),
                }

            # ── Operational Stats ───────────────────────────────────────
            r7 = await conn.execute(text("""
                SELECT COUNT(*) FROM strategies
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """))
            strat_row = r7.fetchone()
            snapshot["operations"] = {
                "n_strategies_24h": int(strat_row[0] or 0) if strat_row else 0,
            }

            # ── Replay Integrity ────────────────────────────────────────
            r8 = await conn.execute(text("""
                SELECT integrity_score, n_violations
                FROM replay_integrity
                ORDER BY checked_at DESC LIMIT 1
            """))
            replay_row = r8.fetchone()
            if replay_row:
                snapshot["replay_integrity"] = {
                    "integrity_score": float(replay_row[0] or 0),
                    "n_violations": int(replay_row[1] or 0),
                }

            # ── Execution Realism ───────────────────────────────────────
            r9 = await conn.execute(text("""
                SELECT
                    avg_expected_slippage_bps,
                    avg_fill_probability,
                    execution_degradation_score
                FROM execution_realism
                ORDER BY simulated_at DESC LIMIT 1
            """))
            exec_row = r9.fetchone()
            if exec_row:
                snapshot["execution_realism"] = {
                    "avg_slippage_bps": float(exec_row[0] or 0),
                    "avg_fill_probability": float(exec_row[1] or 0),
                    "execution_degradation": float(exec_row[2] or 0),
                }

    except Exception as e:
        logger.warning(f"Checkpoint capture error: {e}")
        snapshot["error"] = str(e)

    return snapshot


async def _log_checkpoint(db: TimescaleClient, snapshot: dict) -> None:
    """Persist checkpoint snapshot to the database."""
    try:
        await db._execute_insert(
            """
            INSERT INTO economic_efficiency_analysis
                (id, analyzed_at, composite_analysis, metadata, expectancy)
            VALUES
                (:id, :analyzed_at, CAST(:composite AS jsonb), CAST(:metadata AS jsonb), :expectancy)
            """,
            {
                "id": uuid.uuid4().hex[:16],
                "analyzed_at": datetime.now(timezone.utc),
                "composite": json.dumps(snapshot, default=str),
                "metadata": json.dumps({
                    "type": "checkpoint",
                    "checkpoint_num": snapshot["checkpoint"],
                    "elapsed_hours": snapshot["elapsed_hours"],
                }),
                "expectancy": snapshot.get("economic_quality", {}).get("avg_expectancy", 0),
            },
        )
    except Exception as e:
        logger.warning(f"Checkpoint persist failed: {e}")


async def _capture_runtime_metrics(db: TimescaleClient, tasks: list[asyncio.Task], elapsed_seconds: float) -> None:
    """Persist continuous Phase 29 runtime telemetry every five minutes."""
    try:
        async with db.engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS phase29_runtime_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    interval_seconds INT NOT NULL,
                    metrics JSONB NOT NULL DEFAULT CAST('{}' AS jsonb)
                )
            """))

            stats = await conn.execute(text("""
                SELECT
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE created_at > NOW() - INTERVAL '5 minutes'), 0) AS strategies_generated,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status = 'pending_code'), 0) AS pending_code_count,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status = 'pending_backtest'), 0) AS pending_backtest_count,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('validated', 'elite', 'promoted', 'live')), 0) AS validated_count,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('validated', 'elite', 'promoted', 'live', 'research_candidate')), 0) AS active_count,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('retired', 'dead')), 0) AS retired_count,
                    COALESCE((SELECT COUNT(*) FROM copy_execution_log WHERE status = 'filled' AND created_at > NOW() - INTERVAL '5 minutes'), 0) AS trades_executed,
                    COALESCE((SELECT COUNT(*) FROM scout_economic_attribution WHERE created_at > NOW() - INTERVAL '5 minutes'), 0) AS attribution_records,
                    COALESCE((SELECT COUNT(*) FROM strategies WHERE status IN ('repair_candidate', 'research_candidate')), 0) AS mutation_candidates,
                    COALESCE((SELECT COALESCE(n_strategies, 0) FROM capital_allocation ORDER BY computed_at DESC LIMIT 1), 0) AS portfolio_participants,
                    COALESCE((SELECT MAX(dynamic_trust_score) - MIN(dynamic_trust_score) FROM source_performance_log WHERE updated_at > NOW() - INTERVAL '24 hours'), 0) AS scout_trust_divergence,
                    COALESCE((SELECT integrity_score FROM replay_integrity ORDER BY checked_at DESC LIMIT 1), 0) AS replay_integrity_score,
                    COALESCE((SELECT n_violations FROM replay_integrity ORDER BY checked_at DESC LIMIT 1), 0) AS replay_violations
            """))
            row = stats.fetchone()

            metrics = {
                "elapsed_seconds": round(float(elapsed_seconds), 1),
                "strategies_generated": int(row[0] or 0) if row else 0,
                "pending_code_count": int(row[1] or 0) if row else 0,
                "pending_backtest_count": int(row[2] or 0) if row else 0,
                "validated_count": int(row[3] or 0) if row else 0,
                "active_count": int(row[4] or 0) if row else 0,
                "retired_count": int(row[5] or 0) if row else 0,
                "trades_executed": int(row[6] or 0) if row else 0,
                "attribution_records": int(row[7] or 0) if row else 0,
                "mutation_candidates": int(row[8] or 0) if row else 0,
                "portfolio_participants": int(row[9] or 0) if row else 0,
                "scout_trust_divergence": float(row[10] or 0) if row else 0.0,
                "replay_integrity_score": float(row[11] or 0) if row else 0.0,
                "replay_violations": int(row[12] or 0) if row else 0,
                "async_task_count": sum(1 for task in tasks if not task.done()),
            }

            await conn.execute(text("""
                INSERT INTO phase29_runtime_metrics (captured_at, interval_seconds, metrics)
                VALUES (NOW(), :interval_seconds, CAST(:metrics AS jsonb))
            """), {
                "interval_seconds": 300,
                "metrics": json.dumps(metrics),
            })

            logger.info(
                "Phase 29 runtime telemetry: "
                f"generated={metrics['strategies_generated']} pending_code={metrics['pending_code_count']} "
                f"pending_backtest={metrics['pending_backtest_count']} validated={metrics['validated_count']} "
                f"active={metrics['active_count']} trades={metrics['trades_executed']} "
                f"attr={metrics['attribution_records']} mutation_candidates={metrics['mutation_candidates']}"
            )
    except Exception as e:
        logger.warning(f"Runtime metrics capture failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

async def _generate_economic_efficiency_report(db: TimescaleClient) -> str:
    """PHASE29_ECONOMIC_EFFICIENCY_REPORT.md"""
    lines = [
        "# Phase 29 — Economic Efficiency Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## 29A — Trade Quality Metrics",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT expectancy, win_loss_asymmetry, slippage_adjusted_edge,
                       risk_adjusted_return
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                lines.append(f"| Expectancy | {float(row[0] or 0):.6f} |")
                lines.append(f"| Win/Loss Asymmetry | {float(row[1] or 1.0):.4f} |")
                lines.append(f"| Slippage-Adjusted Edge | {float(row[2] or 0):.6f} |")
                lines.append(f"| Risk-Adjusted Return | {float(row[3] or 0):.4f} |")
                # trade_clustering is stored inside composite_analysis JSONB
                try:
                    r_tc = await conn.execute(text("""
                        SELECT composite_analysis->'trade_quality'->>'trade_clustering'
                        FROM economic_efficiency_analysis
                        ORDER BY analyzed_at DESC LIMIT 1
                    """))
                    tc_row = r_tc.fetchone()
                    tc_val = float(tc_row[0] or 0) if tc_row and tc_row[0] else 0
                    lines.append(f"| Trade Clustering | {tc_val:.4f} |")
                except Exception:
                    pass

            lines.extend(["", "## 29B — Long-Horizon Fitness Windows", "| Window | Avg Fitness | Avg Sharpe | Avg Sortino | Trend |", "|--------|-------------|------------|-------------|-------|"])
            r2 = await conn.execute(text("""
                SELECT window_hours, avg_composite_fitness, avg_sharpe, avg_sortino, fitness_trend
                FROM economic_fitness_windows
                WHERE computed_at > NOW() - INTERVAL '1 hour'
                ORDER BY window_hours
            """))
            for row2 in r2.fetchall():
                lines.append(f"| {int(row2[0])}h | {float(row2[1] or 0):.4f} | {float(row2[2] or 0):.4f} | {float(row2[3] or 0):.4f} | {float(row2[4] or 0):.4f} |")

            lines.extend(["", "## 29C — Capital Efficiency", "| Metric | Value |", "|--------|-------|"])
            r3 = await conn.execute(text("""
                SELECT return_per_drawdown, capital_velocity
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row3 = r3.fetchone()
            if row3:
                lines.append(f"| Return per Drawdown | {float(row3[0] or 0):.6f} |")
                lines.append(f"| Capital Velocity | {float(row3[1] or 0):.4f} |")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_capital_preservation_report(db: TimescaleClient) -> str:
    """PHASE29_CAPITAL_PRESERVATION_REPORT.md"""
    lines = [
        "# Phase 29 — Capital Preservation Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Drawdown & Recovery Analysis",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT drawdown_persistence_hours, recovery_efficiency,
                       cascading_failure_risk, concentration_instability,
                       portfolio_contagion_risk
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                lines.append(f"| Drawdown Persistence (hours) | {float(row[0] or 0):.2f} |")
                lines.append(f"| Recovery Efficiency | {float(row[1] or 1.0):.4f} |")
                lines.append(f"| Cascading Failure Risk | {float(row[2] or 0):.4f} |")
                lines.append(f"| Concentration Instability | {float(row[3] or 0):.4f} |")
                lines.append(f"| Portfolio Contagion Risk | {float(row[4] or 0):.4f} |")

            r2 = await conn.execute(text("""
                SELECT drawdown_pct, action_taken
                FROM capital_preservation_state
                ORDER BY checked_at DESC LIMIT 5
            """))
            lines.extend(["", "## Recent Capital Preservation Actions", "| Drawdown | Action |", "|----------|--------|"])
            for row2 in r2.fetchall():
                lines.append(f"| {float(row2[0] or 0):.4f} | {row2[1] or 'none'} |")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_mutation_evolution_report(db: TimescaleClient) -> str:
    """PHASE29_MUTATION_EVOLUTION_REPORT.md"""
    lines = [
        "# Phase 29 — Mutation Evolution Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Mutation Family Survival",
        "| Mutation Type | Applications | Survival Rate | Fitness Contribution |",
        "|---------------|-------------|---------------|---------------------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT mutation_type, total_applications, survival_rate, avg_fitness_contribution
                FROM mutation_survival_log
                ORDER BY total_applications DESC
                LIMIT 20
            """))
            for row in r.fetchall():
                lines.append(f"| {row[0]} | {int(row[1] or 0)} | {float(row[2] or 0):.4f} | {float(row[3] or 0):.4f} |")

            r2 = await conn.execute(text("""
                SELECT dominant_mutation_family, collapsing_families, exploration_ratio
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row2 = r2.fetchone()
            if row2:
                lines.extend(["", "## Evolutionary State", f"- **Dominant Family:** {row2[0] or 'none'}"])
                collapsing = json.loads(row2[1]) if isinstance(row2[1], str) else (row2[1] or [])
                lines.append(f"- **Collapsing Families:** {collapsing}")
                lines.append(f"- **Exploration Ratio:** {float(row2[2] or 0.5):.4f}")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_scout_predictive_value_report(db: TimescaleClient) -> str:
    """PHASE29_SCOUT_PREDICTIVE_VALUE_REPORT.md"""
    lines = [
        "# Phase 29 — Scout Predictive Value Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Scout Economic Rankings",
        "| Scout | Attributions | Survival Rate | Sharpe Contrib | Economic Score | Contradiction |",
        "|-------|-------------|---------------|----------------|----------------|---------------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT source_scout, n_attributions, survival_rate,
                       avg_sharpe_contribution, economic_score_penalized, contradiction_rate
                FROM scout_predictive_value_log
                WHERE computed_at > NOW() - INTERVAL '24 hours'
                ORDER BY economic_score_penalized DESC
                LIMIT 20
            """))
            for row in r.fetchall():
                lines.append(f"| {row[0]} | {int(row[1] or 0)} | {float(row[2] or 0):.4f} | {float(row[3] or 0):.4f} | {float(row[4] or 0):.4f} | {float(row[5] or 0):.4f} |")

            r2 = await conn.execute(text("""
                SELECT top_scout, worst_scout, predictive_divergence
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row2 = r2.fetchone()
            if row2:
                lines.extend(["", "## Predictive Divergence", f"- **Top Scout:** {row2[0] or 'none'}"])
                lines.append(f"- **Worst Scout:** {row2[1] or 'none'}")
                lines.append(f"- **Predictive Divergence:** {float(row2[2] or 0):.4f}")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_regime_specialization_report(db: TimescaleClient) -> str:
    """PHASE29_REGIME_SPECIALIZATION_REPORT.md"""
    lines = [
        "# Phase 29 — Regime Specialization Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Per-Regime Fitness",
        "| Regime | Observations | Avg Fitness | Avg Sharpe | Avg Sortino | Win Rate | Trades |",
        "|--------|-------------|-------------|------------|-------------|----------|--------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT regime, n_observations, avg_fitness, avg_sharpe,
                       avg_sortino, avg_win_rate, total_trades
                FROM regime_specialization_log
                WHERE recorded_at > NOW() - INTERVAL '24 hours'
                ORDER BY avg_fitness DESC
                LIMIT 20
            """))
            for row in r.fetchall():
                lines.append(f"| {row[0]} | {int(row[1] or 0)} | {float(row[2] or 0):.4f} | {float(row[3] or 0):.4f} | {float(row[4] or 0):.4f} | {float(row[5] or 0):.4f} | {int(row[6] or 0)} |")

            r2 = await conn.execute(text("""
                SELECT n_fragile_organisms, n_cross_regime_survivors,
                       n_volatility_sensitive, n_liquidity_sensitive
                FROM regime_specialization_summary
                ORDER BY computed_at DESC LIMIT 1
            """))
            row2 = r2.fetchone()
            if row2:
                lines.extend(["", "## Specialization Summary", "| Category | Count |", "|----------|-------|"])
                lines.append(f"| Fragile Organisms (1 regime only) | {int(row2[0] or 0)} |")
                lines.append(f"| Cross-Regime Survivors (≥3 regimes) | {int(row2[1] or 0)} |")
                lines.append(f"| Volatility-Sensitive | {int(row2[2] or 0)} |")
                lines.append(f"| Liquidity-Sensitive | {int(row2[3] or 0)} |")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_execution_realism_report(db: TimescaleClient) -> str:
    """PHASE29_EXECUTION_REALISM_REPORT.md"""
    lines = [
        "# Phase 29 — Execution Realism Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Execution Quality Metrics",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT avg_expected_slippage_bps, avg_fill_probability,
                       avg_simulated_latency_ms, execution_degradation_score
                FROM execution_realism
                ORDER BY simulated_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                lines.append(f"| Avg Slippage (bps) | {float(row[0] or 0):.4f} |")
                lines.append(f"| Avg Fill Probability | {float(row[1] or 0):.4f} |")
                lines.append(f"| Avg Latency (ms) | {float(row[2] or 0):.2f} |")
                lines.append(f"| Execution Degradation | {float(row[3] or 0):.4f} |")

            r2 = await conn.execute(text("""
                SELECT execution_degradation, spread_sensitivity, liquidity_degradation_trend
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            row2 = r2.fetchone()
            if row2:
                lines.append(f"| Execution Degradation (composite) | {float(row2[0] or 0):.4f} |")
                lines.append(f"| Spread Sensitivity | {float(row2[1] or 0):.4f} |")
                lines.append(f"| Liquidity Degradation Trend | {float(row2[2] or 0):.4f} |")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_long_horizon_survival_report(db: TimescaleClient) -> str:
    """PHASE29_LONG_HORIZON_SURVIVAL_REPORT.md"""
    lines = [
        "# Phase 29 — Long-Horizon Survival Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Rolling Fitness Windows",
        "| Window | Strategies | Avg Fitness | Median | Top 10% | Bottom 10% | Trend | Mutation Survival |",
        "|--------|-----------|-------------|--------|---------|------------|-------|-------------------|",
    ]
    try:
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT window_hours, n_strategies, avg_composite_fitness,
                       median_composite_fitness, top_decile_fitness,
                       bottom_decile_fitness, fitness_trend, mutation_survival_rate
                FROM economic_fitness_windows
                WHERE computed_at > NOW() - INTERVAL '1 hour'
                ORDER BY window_hours
            """))
            for row in r.fetchall():
                lines.append(f"| {int(row[0])}h | {int(row[1] or 0)} | {float(row[2] or 0):.4f} | {float(row[3] or 0):.4f} | {float(row[4] or 0):.4f} | {float(row[5] or 0):.4f} | {float(row[6] or 0):.4f} | {float(row[7] or 0):.4f} |")

            r2 = await conn.execute(text("""
                SELECT n_strategies, avg_composite_fitness, avg_sharpe, avg_sortino,
                       avg_calmar, avg_expectancy
                FROM economic_fitness_windows
                WHERE window_hours = 24
                ORDER BY computed_at DESC LIMIT 5
            """))
            rows2 = r2.fetchall()
            if rows2:
                lines.extend(["", "## 24h Fitness Evolution (Last 5 Snapshots)", "| Snapshot | Strategies | Fitness | Sharpe | Sortino | Calmar | Expectancy |", "|----------|-----------|---------|--------|---------|--------|------------|"])
                for i, row2 in enumerate(rows2, 1):
                    lines.append(f"| {i} | {int(row2[0] or 0)} | {float(row2[1] or 0):.4f} | {float(row2[2] or 0):.4f} | {float(row2[3] or 0):.4f} | {float(row2[4] or 0):.4f} | {float(row2[5] or 0):.6f} |")

    except Exception as e:
        lines.append(f"| Error | {e} |")

    lines.append("")
    return "\n".join(lines)


async def _generate_adaptive_economic_certification(db: TimescaleClient) -> str:
    """PHASE29_ADAPTIVE_ECONOMIC_CERTIFICATION.md"""
    cert_pass = True
    findings = []
    failures = []

    try:
        async with db.engine.connect() as conn:
            # 1. Trading efficiency improves over time
            r = await conn.execute(text("""
                SELECT expectancy, risk_adjusted_return
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 5
            """))
            exps = [float(row[0] or 0) for row in r.fetchall()]
            if len(exps) >= 2 and exps[0] > exps[-1]:
                findings.append("✅ Trading efficiency is IMPROVING over time")
            elif len(exps) >= 2:
                findings.append("⚠️ Trading efficiency is NOT improving — may be degrading")

            # 2. Weak organisms naturally decay
            r2 = await conn.execute(text("""
                SELECT COUNT(*) FROM strategies
                WHERE lifecycle_state IN ('retired', 'dead')
                  AND created_at > NOW() - INTERVAL '24 hours'
            """))
            decay_row = r2.fetchone()
            n_decayed = int(decay_row[0] or 0) if decay_row else 0
            findings.append(f"{'✅' if n_decayed > 0 else '⚠️'} Weak organisms decaying: {n_decayed} retired/dead in 24h")

            # 3. Dominant mutation families emerge
            r3 = await conn.execute(text("""
                SELECT dominant_mutation_family
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            dom_row = r3.fetchone()
            dominant = str(dom_row[0] or "none") if dom_row else "none"
            if dominant != "none":
                findings.append(f"✅ Dominant mutation family emerged: {dominant}")
            else:
                findings.append("⚠️ No dominant mutation family — exploration may be too diffuse")

            # 4. Scout predictive value diverges
            r4 = await conn.execute(text("""
                SELECT predictive_divergence
                FROM economic_efficiency_analysis
                ORDER BY analyzed_at DESC LIMIT 1
            """))
            div_row = r4.fetchone()
            divergence = float(div_row[0] or 0) if div_row else 0
            if divergence > 0.1:
                findings.append(f"✅ Scout predictive value diverging meaningfully: {divergence:.4f}")
            else:
                findings.append(f"⚠️ Scout predictive divergence low: {divergence:.4f}")

            # 5. Portfolio survivability improves
            r5 = await conn.execute(text("""
                SELECT portfolio_survivability, diversification_score
                FROM portfolio_evolution_log
                ORDER BY created_at DESC LIMIT 3
            """))
            survs = [float(row[0] or 0) for row in r5.fetchall()]
            if len(survs) >= 2 and survs[0] >= survs[-1]:
                findings.append("✅ Portfolio survivability stable or improving")
            else:
                findings.append("⚠️ Portfolio survivability may be degrading")

            # 6. Capital preservation remains stable
            r6 = await conn.execute(text("""
                SELECT drawdown_pct
                FROM capital_preservation_state
                ORDER BY checked_at DESC LIMIT 1
            """))
            dd_row = r6.fetchone()
            current_dd = float(dd_row[0] or 0) if dd_row else 0
            if current_dd < 0.15:
                findings.append(f"✅ Capital preservation stable (drawdown: {current_dd:.2%})")
            else:
                failures.append(f"❌ Capital preservation critical (drawdown: {current_dd:.2%})")

            # 7. Regime specialization emerges
            r7 = await conn.execute(text("""
                SELECT COUNT(DISTINCT regime) FROM regime_specialization_log
                WHERE recorded_at > NOW() - INTERVAL '24 hours'
            """))
            regime_row = r7.fetchone()
            n_regimes = int(regime_row[0] or 0) if regime_row else 0
            if n_regimes >= 3:
                findings.append(f"✅ Regime specialization emerging across {n_regimes} regimes")
            else:
                findings.append(f"⚠️ Limited regime specialization ({n_regimes} regimes)")

            # 8. Replay determinism
            r8 = await conn.execute(text("""
                SELECT integrity_score, n_violations
                FROM replay_integrity
                ORDER BY checked_at DESC LIMIT 1
            """))
            rep_row = r8.fetchone()
            if rep_row:
                replay_score = float(rep_row[0] or 0)
                n_violations = int(rep_row[1] or 0)
                if replay_score > 0.9 and n_violations == 0:
                    findings.append(f"✅ Replay determinism intact (score: {replay_score:.4f}, violations: 0)")
                else:
                    findings.append(f"⚠️ Replay concerns (score: {replay_score:.4f}, violations: {n_violations})")

    except Exception as e:
        failures.append(f"❌ Certification error: {e}")

    pass_status = len(failures) == 0

    lines = [
        "# Phase 29 — Adaptive Economic Certification",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        f"## Status: {'✅ PASS' if pass_status else '❌ FAIL'}",
        "",
        "## Findings",
    ]
    lines.extend(findings)
    if failures:
        lines.extend(["", "## Failures"])
        lines.extend(failures)
    lines.append("")

    return "\n".join(lines)


async def _write_report(path: Path, content: str) -> None:
    """Write a report file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Report written: {path.name}")


async def _generate_all_reports(db: TimescaleClient) -> None:
    """Generate all 8 Phase 29 reports."""
    reports = {
        "PHASE29_HOTFIX_RUNTIME_REPORT.md": _generate_economic_efficiency_report(db),
        "PHASE29_PIPELINE_FLOW_REPORT.md": _generate_long_horizon_survival_report(db),
        "PHASE29_ECONOMIC_THROUGHPUT_REPORT.md": _generate_economic_efficiency_report(db),
        "PHASE29_EXECUTION_DENSITY_REPORT.md": _generate_execution_realism_report(db),
        "PHASE29_MUTATION_ECOLOGY_REPORT.md": _generate_mutation_evolution_report(db),
        "PHASE29_PORTFOLIO_EVOLUTION_REPORT.md": _generate_capital_preservation_report(db),
        "PHASE29_ATTRIBUTION_CERTIFICATION.md": _generate_scout_predictive_value_report(db),
        "PHASE29_HOTFIX_CERTIFICATION.md": _generate_adaptive_economic_certification(db),
    }

    async def _write_named(path: str, content_future: asyncio.Future | str) -> None:
        content = await content_future if asyncio.iscoroutine(content_future) else content_future
        await _write_report(REPORT_DIR / path, content)

    await asyncio.gather(*(_write_named(name, coro) for name, coro in reports.items()))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 29 — 12-Hour Economic Evolution Soak")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=720,
        help="How long to run the soak (default: 720 = 12 hours)",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=CHECKPOINT_INTERVAL,
        help="Seconds between checkpoints (default: 1800 = 30 minutes)",
    )
    parser.add_argument(
        "--generate-reports",
        action="store_true",
        default=True,
        help="Generate 8 Phase 29 reports on completion",
    )
    args = parser.parse_args()

    logger.info(f"╔{'═' * 70}╗")
    logger.info(f"║{'  PHASE 29 — 12-HOUR ECONOMIC EVOLUTION SOAK':^72}║")
    logger.info(f"║{'  Duration: {} minutes'.format(args.duration_minutes):<72}║")
    logger.info(f"║{'  Checkpoint Interval: {}s'.format(args.checkpoint_interval):<72}║")
    logger.info(f"╚{'═' * 70}╝")

    settings = get_settings()
    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()
    redis_client = Redis.from_url(settings.redis_url)

    agents = _build_agents(redis_client, db_client)

    # Phase 24: Soak monitoring
    monitor = SoakMonitor(db_client, redis_client, interval_seconds=300)
    try:
        await monitor.start()
        logger.info("SoakMonitor started — capturing metrics every 300s")
    except Exception as e:
        logger.error(f"SoakMonitor failed: {e} — continuing without monitoring")
        monitor = None

    logger.info("Starting Phase 29 autonomous cycle with ALL features enabled")
    tasks = await _start_agents(agents)

    runtime_seconds = max(60, args.duration_minutes) * 60
    checkpoint_interval = max(60, args.checkpoint_interval)
    checkpoint_num = 0
    runtime_metrics_interval = 300
    _last_runtime_metrics: float = 0.0

    try:
        start = time.time()
        _reported: set[int] = set()
        _last_checkpoint: float = 0.0

        while True:
            elapsed = time.time() - start
            elapsed_hours = elapsed / 3600

            if elapsed >= runtime_seconds:
                logger.info("Phase 29 soak duration reached; shutting down")
                break

            # ── Checkpoint every N seconds ──────────────────────────────
            if elapsed - _last_checkpoint >= checkpoint_interval:
                checkpoint_num += 1
                logger.info(f"── Checkpoint {checkpoint_num} (elapsed: {elapsed_hours:.2f}h) ──")
                snapshot = await _capture_checkpoint(db_client, checkpoint_num, elapsed_hours)
                await _log_checkpoint(db_client, snapshot)

                # Log summary
                eq = snapshot.get("economic_quality", {})
                dd = snapshot.get("capital_preservation", {})
                logger.info(
                    f"  Expectancy: {eq.get('avg_expectancy', 0):.6f}  |  "
                    f"Drawdown: {dd.get('current_drawdown_pct', 0):.4f}  |  "
                    f"Mutations: {snapshot.get('mutation_fitness', {}).get('total_families', 0)}  |  "
                    f"Strategies/24h: {snapshot.get('operations', {}).get('n_strategies_24h', 0)}"
                )

                _last_checkpoint = elapsed

            if elapsed - _last_runtime_metrics >= runtime_metrics_interval:
                await _capture_runtime_metrics(db_client, tasks, elapsed)
                _last_runtime_metrics = elapsed

            # ── Monitor agent tasks ─────────────────────────────────────
            for i, task in enumerate(tasks):
                if task.done() and i not in _reported:
                    agent = agents[i] if i < len(agents) else None
                    agent_name = getattr(agent, "name", f"agent_{i}") if agent else f"task_{i}"
                    exc = task.exception()
                    if task.cancelled():
                        logger.warning(f"Task cancelled — {agent_name}")
                    elif exc is not None:
                        logger.warning(f"Task died — {agent_name}: {exc}")
                    else:
                        logger.warning(f"Task completed early — {agent_name}")

                    # Auto-restart
                    if agent is not None:
                        try:
                            await agent.stop()
                            await agent.start()
                            if agent._main_task and not agent._main_task.done():
                                tasks[i] = agent._main_task
                                _reported.discard(i)
                                logger.info(f"Agent restarted — {agent_name}")
                        except Exception as restart_exc:
                            logger.error(f"Restart failed — {agent_name}: {restart_exc}")
                    _reported.add(i)

            await asyncio.sleep(5)

    finally:
        if monitor:
            await monitor.stop()
        await _stop_agents(agents)

        # ── Generate Reports ────────────────────────────────────────────
        if args.generate_reports:
            logger.info("Generating 8 Phase 29 reports...")
            await _generate_all_reports(db_client)
            logger.info("All Phase 29 reports generated ✅")

        try:
            await redis_client.aclose()
        except Exception as e:
            logger.warning(f"Redis close: {e}")
        try:
            await db_client.close()
        except Exception as e:
            logger.warning(f"DB close: {e}")

    logger.info("Phase 29 soak complete.")


if __name__ == "__main__":
    asyncio.run(main())
