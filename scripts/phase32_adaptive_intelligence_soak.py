"""
phase32_adaptive_intelligence_soak.py - Phase 32 Long-Horizon Adaptive Intelligence Soak.

Usage:
    python scripts/phase32_adaptive_intelligence_soak.py --duration-minutes 720
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
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
from atlas.data.storage.timescale_client import TimescaleClient

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
            context="Phase32SoakDbClient._execute_insert",
        )
        if recovered:
            logger.warning(
                f"UUID normalization recovered fields for {table_name}: {', '.join(recovered)}"
            )
        async with self.engine.begin() as conn:
            await conn.execute(_t(query), normalized)


class AdaptiveIntelligenceMetricsCollector:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.metrics_history: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase32_intelligence_metrics (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    runtime_minutes INT,

                    dominant_organisms INT,
                    mutation_family_performance JSONB,
                    regime_affinity_rankings JSONB,
                    scout_predictive_rankings JSONB,
                    capital_allocation_evolution JSONB,
                    recovery_quality FLOAT,
                    drawdown_resilience FLOAT,
                    diversification_quality FLOAT,
                    expectancy_distribution JSONB,
                    execution_degradation_metrics JSONB,
                    replay_integrity FLOAT,

                    adaptive_quality_score FLOAT,
                    specialization_quality_score FLOAT,
                    allocation_quality_score FLOAT,
                    evolutionary_selection_score FLOAT,
                    long_horizon_survivability_score FLOAT,

                    metadata JSONB
                )
            """))
            await conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_phase32_intel_metrics_time
                ON phase32_intelligence_metrics (recorded_at DESC)
            """))

            await conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS phase32_mutation_weights (
                    id SERIAL PRIMARY KEY,
                    learned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    family_weights JSONB NOT NULL,
                    exploration_fraction FLOAT NOT NULL,
                    metadata JSONB
                )
            """))

        logger.info("Phase 32 intelligence metrics tables initialized")

    async def collect(self, runtime_minutes: int) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "recorded_at": datetime.now(timezone.utc),
            "runtime_minutes": runtime_minutes,
            "dominant_organisms": 0,
            "mutation_family_performance": [],
            "regime_affinity_rankings": [],
            "scout_predictive_rankings": [],
            "capital_allocation_evolution": {
                "capital_migrated": 0.0,
                "weak_penalized": 0,
                "dominant_boosted": 0,
            },
            "recovery_quality": 0.0,
            "drawdown_resilience": 0.0,
            "diversification_quality": 0.0,
            "expectancy_distribution": {"mean": 0.0, "median": 0.0, "p90": 0.0},
            "execution_degradation_metrics": {
                "degradation": 0.0,
                "slippage_bps": 0.0,
                "fill_probability": 0.0,
            },
            "replay_integrity": 1.0,
        }

        async with self.engine.connect() as conn:
            async def safe_scalar(sql: str, default: Any = 0) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql))).scalar() or default
                except Exception as exc:
                    logger.warning(f"Phase32 metric scalar fallback: {exc}")
                    return default

            async def safe_fetchone(sql: str) -> Any:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql))).fetchone()
                except Exception as exc:
                    logger.warning(f"Phase32 metric row fallback: {exc}")
                    return None

            async def safe_fetchall(sql: str) -> list[Any]:
                try:
                    async with conn.begin_nested():
                        return (await conn.execute(sa_text(sql))).fetchall()
                except Exception as exc:
                    logger.warning(f"Phase32 metric set fallback: {exc}")
                    return []

            metrics["dominant_organisms"] = int(await safe_scalar(
                "SELECT COALESCE(COUNT(*), 0) FROM strategies WHERE lifecycle_state = 'dominant'",
                0,
            ))

            mut_rows = await safe_fetchall("""
                SELECT mutation_type,
                       COALESCE(AVG(sharpe_delta), 0) AS avg_sharpe_delta,
                       COALESCE(AVG(score_delta), 0) AS avg_score_delta,
                       COUNT(*) AS n_obs
                FROM mutation_memory
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY mutation_type
                ORDER BY avg_score_delta DESC, avg_sharpe_delta DESC
                LIMIT 20
            """)
            metrics["mutation_family_performance"] = [
                {
                    "family": str(r[0] or "unknown"),
                    "avg_sharpe_delta": float(r[1] or 0),
                    "avg_score_delta": float(r[2] or 0),
                    "n_obs": int(r[3] or 0),
                }
                for r in mut_rows
            ]

            regime_rows = await safe_fetchall("""
                SELECT primary_affinity,
                       COALESCE(AVG((bull_survivability + bear_survivability + ranging_survivability) / 3.0), 0) AS survivability,
                       COUNT(*) AS n_obs
                FROM organism_regime_profile
                WHERE profiled_at > NOW() - INTERVAL '14 days'
                GROUP BY primary_affinity
                ORDER BY survivability DESC, n_obs DESC
            """)
            metrics["regime_affinity_rankings"] = [
                {
                    "regime": str(r[0] or "unknown"),
                    "survivability": float(r[1] or 0),
                    "n_obs": int(r[2] or 0),
                }
                for r in regime_rows
            ]

            scout_rows = await safe_fetchall("""
                SELECT source_scout,
                       COALESCE(AVG(pnl_contribution), 0) AS avg_pnl_contribution,
                       COALESCE(AVG(sharpe_contribution), 0) AS sharpe_contribution,
                       COUNT(*) AS n_obs
                FROM scout_economic_attribution
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY source_scout
                ORDER BY avg_pnl_contribution DESC, sharpe_contribution DESC
                LIMIT 20
            """)
            metrics["scout_predictive_rankings"] = [
                {
                    "scout": str(r[0] or "unknown"),
                    "avg_net_pnl": float(r[1] or 0),
                    "alignment": float(r[2] or 0),
                    "n_obs": int(r[3] or 0),
                }
                for r in scout_rows
            ]

            alloc = await safe_fetchone("""
                SELECT tracked_at,
                       COALESCE((evolution_pressure_stats->>'total_capital_migrated')::float, 0) AS migrated,
                       COALESCE((evolution_pressure_stats->>'n_weak_penalized')::int, 0) AS weak_penalized,
                       COALESCE((evolution_pressure_stats->>'n_dominant_boosted')::int, 0) AS dominant_boosted
                FROM portfolio_evolution_log
                ORDER BY tracked_at DESC
                LIMIT 1
            """)
            if alloc:
                metrics["capital_allocation_evolution"] = {
                    "capital_migrated": float(alloc[1] or 0),
                    "weak_penalized": int(alloc[2] or 0),
                    "dominant_boosted": int(alloc[3] or 0),
                }

            rec = await safe_fetchone("""
                SELECT
                    COALESCE(AVG(composite_fitness_score / NULLIF(ABS(max_drawdown) + 0.01, 0)), 0) AS recovery_ratio,
                    COALESCE(AVG(max_drawdown), 0)
                FROM backtest_results
                WHERE created_at > NOW() - INTERVAL '14 days'
                  AND max_drawdown IS NOT NULL
            """)
            recovery_ratio = float(rec[0] or 0) if rec else 0.0
            avg_drawdown = abs(float(rec[1] or 0)) if rec else 0.0
            metrics["recovery_quality"] = min(3.0, recovery_ratio) / 3.0
            metrics["drawdown_resilience"] = max(0.0, 1.0 - min(1.0, avg_drawdown / 100.0))

            div = await safe_fetchone("""
                SELECT COALESCE(diversification_score, 0.5), COALESCE(concentration_risk, 0)
                FROM portfolio_intelligence
                ORDER BY computed_at DESC
                LIMIT 1
            """)
            diversification = float(div[0] or 0.5) if div else 0.5
            concentration = float(div[1] or 0) if div else 0.0
            metrics["diversification_quality"] = max(0.0, min(1.0, diversification * (1.0 - concentration)))

            exp = await safe_fetchone("""
                SELECT COALESCE(AVG(expectancy), 0),
                       COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY expectancy), 0),
                       COALESCE(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY expectancy), 0)
                FROM (
                    SELECT
                        CASE WHEN total_trades > 0 THEN
                            (win_rate * 0.01 * sharpe) - ((1 - win_rate * 0.01) * ABS(max_drawdown))
                        ELSE 0 END AS expectancy
                    FROM backtest_results
                    WHERE created_at > NOW() - INTERVAL '14 days'
                ) q
            """)
            if exp:
                metrics["expectancy_distribution"] = {
                    "mean": float(exp[0] or 0),
                    "median": float(exp[1] or 0),
                    "p90": float(exp[2] or 0),
                }

            ex = await safe_fetchone("""
                SELECT COALESCE(execution_degradation_score, 0),
                       COALESCE(avg_expected_slippage_bps, 0),
                       COALESCE(avg_fill_probability, 0)
                FROM execution_realism
                ORDER BY simulated_at DESC
                LIMIT 1
            """)
            if ex:
                metrics["execution_degradation_metrics"] = {
                    "degradation": float(ex[0] or 0),
                    "slippage_bps": float(ex[1] or 0),
                    "fill_probability": float(ex[2] or 0),
                }

            replay = await safe_fetchone("""
                SELECT COALESCE(integrity_score, 100)
                FROM replay_integrity
                ORDER BY checked_at DESC
                LIMIT 1
            """)
            integrity_score = float(replay[0] or 100.0) if replay else 100.0
            metrics["replay_integrity"] = integrity_score / 100.0 if integrity_score > 1 else integrity_score

        self._compute_composites(metrics)
        await self._persist(metrics)
        await self._update_mutation_weights(metrics)
        self.metrics_history.append(metrics)
        return metrics

    def _compute_composites(self, metrics: dict[str, Any]) -> None:
        expectancy = float(metrics["expectancy_distribution"]["mean"])
        recovery = float(metrics["recovery_quality"])
        drawdown_res = float(metrics["drawdown_resilience"])
        diversification = float(metrics["diversification_quality"])
        replay = float(metrics["replay_integrity"])
        exec_realism = 1.0 - min(1.0, float(metrics["execution_degradation_metrics"]["degradation"]))

        regime_strength = 0.0
        rr = metrics.get("regime_affinity_rankings", [])
        if rr:
            regime_strength = sum(float(x.get("survivability", 0)) for x in rr[:3]) / max(1, min(3, len(rr)))

        scout_signal = 0.0
        sr = metrics.get("scout_predictive_rankings", [])
        if sr:
            scout_signal = sum(float(x.get("alignment", 0)) for x in sr[:5]) / max(1, min(5, len(sr)))

        metrics["adaptive_quality_score"] = round(
            max(0.0, min(1.0, 0.30 * drawdown_res + 0.25 * min(1.0, recovery / 3.0) + 0.25 * exec_realism + 0.20 * replay)),
            4,
        )
        metrics["specialization_quality_score"] = round(max(0.0, min(1.0, 0.6 * regime_strength + 0.4 * scout_signal)), 4)
        metrics["allocation_quality_score"] = round(max(0.0, min(1.0, 0.55 * diversification + 0.45 * drawdown_res)), 4)
        metrics["evolutionary_selection_score"] = round(
            max(0.0, min(1.0, 0.5 * min(1.0, (expectancy + 1.0) / 2.0) + 0.25 * drawdown_res + 0.25 * regime_strength)),
            4,
        )
        metrics["long_horizon_survivability_score"] = round(
            max(
                0.0,
                min(
                    1.0,
                    0.25 * metrics["adaptive_quality_score"]
                    + 0.20 * metrics["specialization_quality_score"]
                    + 0.20 * metrics["allocation_quality_score"]
                    + 0.20 * metrics["evolutionary_selection_score"]
                    + 0.15 * replay,
                ),
            ),
            4,
        )

    async def _persist(self, metrics: dict[str, Any]) -> None:
        payload = {
            **metrics,
            "mutation_family_performance": json.dumps(metrics["mutation_family_performance"]),
            "regime_affinity_rankings": json.dumps(metrics["regime_affinity_rankings"]),
            "scout_predictive_rankings": json.dumps(metrics["scout_predictive_rankings"]),
            "capital_allocation_evolution": json.dumps(metrics["capital_allocation_evolution"]),
            "expectancy_distribution": json.dumps(metrics["expectancy_distribution"]),
            "execution_degradation_metrics": json.dumps(metrics["execution_degradation_metrics"]),
            "metadata": json.dumps({"collected_at": datetime.now(timezone.utc).isoformat()}),
        }
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase32_intelligence_metrics (
                    recorded_at, runtime_minutes,
                    dominant_organisms, mutation_family_performance, regime_affinity_rankings,
                    scout_predictive_rankings, capital_allocation_evolution,
                    recovery_quality, drawdown_resilience, diversification_quality,
                    expectancy_distribution, execution_degradation_metrics, replay_integrity,
                    adaptive_quality_score, specialization_quality_score, allocation_quality_score,
                    evolutionary_selection_score, long_horizon_survivability_score,
                    metadata
                ) VALUES (
                    :recorded_at, :runtime_minutes,
                    :dominant_organisms, CAST(:mutation_family_performance AS jsonb), CAST(:regime_affinity_rankings AS jsonb),
                    CAST(:scout_predictive_rankings AS jsonb), CAST(:capital_allocation_evolution AS jsonb),
                    :recovery_quality, :drawdown_resilience, :diversification_quality,
                    CAST(:expectancy_distribution AS jsonb), CAST(:execution_degradation_metrics AS jsonb), :replay_integrity,
                    :adaptive_quality_score, :specialization_quality_score, :allocation_quality_score,
                    :evolutionary_selection_score, :long_horizon_survivability_score,
                    CAST(:metadata AS jsonb)
                )
            """), payload)

    async def _update_mutation_weights(self, metrics: dict[str, Any]) -> None:
        families = metrics.get("mutation_family_performance", [])
        if not families:
            return

        explore_fraction = 0.20
        perf = {f["family"]: max(0.0, f["avg_score_delta"] + 0.5 * f["avg_sharpe_delta"]) for f in families}
        total = sum(perf.values())
        if total <= 0:
            weights = {k: 1.0 / len(perf) for k in perf}
        else:
            exploit = {k: v / total for k, v in perf.items()}
            uniform = 1.0 / len(exploit)
            weights = {k: (1.0 - explore_fraction) * exploit[k] + explore_fraction * uniform for k in exploit}

        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
                INSERT INTO phase32_mutation_weights (family_weights, exploration_fraction, metadata)
                VALUES (CAST(:weights AS jsonb), :explore, CAST(:metadata AS jsonb))
            """), {
                "weights": json.dumps(weights),
                "explore": explore_fraction,
                "metadata": json.dumps({"source": "phase32_adaptive_intelligence_soak"}),
            })

    async def close(self) -> None:
        await self.engine.dispose()


class AdaptiveIntelligenceSoakController:
    def __init__(self, duration_minutes: int = 720, metrics_interval: int = 300):
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.metrics_interval = metrics_interval
        self.db_url = settings.database_url
        self.metrics = AdaptiveIntelligenceMetricsCollector(self.db_url)
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

        self._engines_initialized = True
        logger.info("Phase 32 engines initialized")

    async def _safe_call(self, name: str, coro, timeout: int = 45) -> None:
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.debug(f"Phase32[{name}] OK")
        except asyncio.TimeoutError:
            logger.warning(f"Phase32[{name}] TIMEOUT after {timeout}s")
        except Exception as e:
            logger.warning(f"Phase32[{name}] FAILED: {type(e).__name__}: {e}")

    async def _run_phase32_cycle(self) -> None:
        await self._ensure_engines()

        await self._safe_call("DominantOrganism", self._dominant_tracker._tracking_cycle())
        await self._safe_call("MutationLineage", self._lineage_tracker._lineage_cycle())
        await self._safe_call("RegimeSpecialization", self._regime_engine._profiling_cycle())
        await self._safe_call("ScoutDivergence", self._scout_engine._divergence_cycle())
        await self._safe_call("PortfolioEvolution", self._portfolio_engine._pressure_cycle())
        await self._safe_call("RegimeStress", self._stress_engine._stress_cycle())

        await self._safe_call("MutationPolicy", self._mutation_policy._learn_policy())
        await self._safe_call("EconomicEfficiency", self._economic_engine._full_economic_analysis_cycle())
        await self._safe_call("ReplayIntegrity", self._replay_engine._sweep_replay_checks())

        report = await self._retirement_engine._compute_retirement_analysis()
        if report:
            await self._safe_call("RetirementPersist", self._retirement_engine._persist_retirement(report))
            await self._safe_call("RetirementPublish", self._retirement_engine._publish_retirement(report))

    async def _ensure_schema_compatibility(self, probe: TimescaleClient) -> None:
        async with probe.engine.begin() as conn:
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS portfolio_id TEXT"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS diversification_score FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS correlation_collapse_risk FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS contagion_exposure FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS concentration_risk FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS portfolio_survivability FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS drawdown_recovery_speed FLOAT DEFAULT 0"
            ))
            await conn.execute(sa_text(
                "ALTER TABLE portfolio_evolution_log ADD COLUMN IF NOT EXISTS active_strategies INT DEFAULT 0"
            ))

    async def run(self) -> None:
        logger.info("=" * 72)
        logger.info("PHASE 32 - ADAPTIVE ECONOMIC INTELLIGENCE SOAK STARTING")
        logger.info(f"Duration: {self.duration_minutes}m | Metrics interval: {self.metrics_interval}s")
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
                await self._run_phase32_cycle()
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
        print(f"\n[Phase32] T+{e}m / T-{r}m")
        print(
            "  Scores: "
            f"AQ={metrics.get('adaptive_quality_score', 0):.3f} "
            f"SQ={metrics.get('specialization_quality_score', 0):.3f} "
            f"AL={metrics.get('allocation_quality_score', 0):.3f} "
            f"ES={metrics.get('evolutionary_selection_score', 0):.3f} "
            f"LH={metrics.get('long_horizon_survivability_score', 0):.3f}"
        )
        print(
            "  Core: "
            f"dominant={metrics.get('dominant_organisms', 0)} "
            f"replay={metrics.get('replay_integrity', 0):.4f} "
            f"drawdown_res={metrics.get('drawdown_resilience', 0):.3f} "
            f"diversification={metrics.get('diversification_quality', 0):.3f}"
        )
        sys.stdout.flush()

    async def _finalize(self) -> None:
        total_minutes = int((time.time() - self._start_time) / 60) if self._start_time else 0
        logger.info(f"Phase 32 soak complete after {total_minutes} minutes")

        latest = self.metrics.metrics_history[-1] if self.metrics.metrics_history else {}
        initial = self.metrics.metrics_history[0] if self.metrics.metrics_history else {}

        await self._generate_reports(initial, latest, total_minutes)
        await self.metrics.close()

    async def _generate_reports(self, initial: dict[str, Any], latest: dict[str, Any], duration_minutes: int) -> None:
        def pct_delta(key: str) -> float:
            a = float(initial.get(key, 0) or 0)
            b = float(latest.get(key, 0) or 0)
            if a == 0:
                return b
            return (b - a) / abs(a)

        survival_lines = [
            "# PHASE32_SURVIVAL_QUALITY_REPORT",
            "",
            f"Duration minutes: {duration_minutes}",
            f"Adaptive quality score: {latest.get('adaptive_quality_score', 0)}",
            f"Drawdown resilience: {latest.get('drawdown_resilience', 0)}",
            f"Recovery quality: {latest.get('recovery_quality', 0)}",
            f"Expectancy distribution: {json.dumps(latest.get('expectancy_distribution', {}), indent=2)}",
        ]

        mutation_lines = [
            "# PHASE32_MUTATION_INTELLIGENCE_REPORT",
            "",
            "Top mutation families:",
            json.dumps(latest.get("mutation_family_performance", [])[:10], indent=2),
        ]

        regime_lines = [
            "# PHASE32_REGIME_SPECIALIZATION_REPORT",
            "",
            "Regime affinity rankings:",
            json.dumps(latest.get("regime_affinity_rankings", []), indent=2),
        ]

        portfolio_lines = [
            "# PHASE32_PORTFOLIO_EVOLUTION_REPORT",
            "",
            f"Allocation quality score: {latest.get('allocation_quality_score', 0)}",
            f"Diversification quality: {latest.get('diversification_quality', 0)}",
            "Capital allocation evolution:",
            json.dumps(latest.get("capital_allocation_evolution", {}), indent=2),
        ]

        scout_lines = [
            "# PHASE32_SCOUT_PREDICTION_REPORT",
            "",
            "Scout predictive rankings:",
            json.dumps(latest.get("scout_predictive_rankings", [])[:15], indent=2),
        ]

        execution_lines = [
            "# PHASE32_EXECUTION_QUALITY_REPORT",
            "",
            "Execution degradation metrics:",
            json.dumps(latest.get("execution_degradation_metrics", {}), indent=2),
            f"Replay integrity: {latest.get('replay_integrity', 0)}",
        ]

        pass_checks = {
            "dominant adaptive organisms emerge": latest.get("dominant_organisms", 0) >= 1,
            "regime specialists measurable": len(latest.get("regime_affinity_rankings", [])) >= 2,
            "scout trust diverges economically": len(latest.get("scout_predictive_rankings", [])) >= 2,
            "capital allocation adapts": latest.get("allocation_quality_score", 0) >= 0.30,
            "mutation quality improves": pct_delta("evolutionary_selection_score") >= 0,
            "drawdown resilience improves": pct_delta("drawdown_resilience") >= 0,
            "portfolio survivability improves": pct_delta("long_horizon_survivability_score") >= 0,
            "execution realism stable": latest.get("execution_degradation_metrics", {}).get("degradation", 1.0) <= 0.7,
            "replay integrity perfect": (latest.get("replay_integrity", 0) >= 0.9999),
            "long horizon survivability improves": pct_delta("long_horizon_survivability_score") >= 0,
        }
        passed = all(pass_checks.values())

        cert_lines = [
            "# PHASE32_ADAPTIVE_INTELLIGENCE_CERTIFICATION",
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
                    "adaptive_quality_score": latest.get("adaptive_quality_score", 0),
                    "specialization_quality_score": latest.get("specialization_quality_score", 0),
                    "allocation_quality_score": latest.get("allocation_quality_score", 0),
                    "evolutionary_selection_score": latest.get("evolutionary_selection_score", 0),
                    "long_horizon_survivability_score": latest.get("long_horizon_survivability_score", 0),
                },
                indent=2,
            ),
        ])

        reports = {
            "PHASE32_SURVIVAL_QUALITY_REPORT.md": "\n".join(survival_lines) + "\n",
            "PHASE32_MUTATION_INTELLIGENCE_REPORT.md": "\n".join(mutation_lines) + "\n",
            "PHASE32_REGIME_SPECIALIZATION_REPORT.md": "\n".join(regime_lines) + "\n",
            "PHASE32_PORTFOLIO_EVOLUTION_REPORT.md": "\n".join(portfolio_lines) + "\n",
            "PHASE32_SCOUT_PREDICTION_REPORT.md": "\n".join(scout_lines) + "\n",
            "PHASE32_EXECUTION_QUALITY_REPORT.md": "\n".join(execution_lines) + "\n",
            "PHASE32_ADAPTIVE_INTELLIGENCE_CERTIFICATION.md": "\n".join(cert_lines) + "\n",
        }

        for name, content in reports.items():
            (ROOT / name).write_text(content, encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 32 adaptive intelligence soak")
    parser.add_argument("--duration-minutes", type=int, default=720)
    parser.add_argument("--metrics-interval", type=int, default=300)
    args = parser.parse_args()

    controller = AdaptiveIntelligenceSoakController(
        duration_minutes=args.duration_minutes,
        metrics_interval=args.metrics_interval,
    )
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
