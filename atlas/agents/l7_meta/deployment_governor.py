"""
deployment_governor.py — L7 Meta Agent for deployment governance.

Capabilities:
- Canary deployments
- Shadow deployments
- Rollout approval gates
- Automatic rollback
- Performance regression detection
- Deployment survivability scoring

Modes:
- paper, shadow, partial-live, live
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from loguru import logger
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent
from atlas.core.selection import tournament_select_unique
from atlas.core.messaging import MessagingClient, Channel


class DeploymentMode(str, Enum):
    PAPER = "paper"
    SHADOW = "shadow"
    PARTIAL_LIVE = "partial_live"
    LIVE = "live"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class DeploymentGovernor(BaseAgent):
    """
    L7 Meta Agent — Governs strategy deployments with safety gates.
    """

    name = "DeploymentGovernor"
    agent_type = "deployment_governor"
    layer = "L7"

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client)
        self.db = db_client
        self.messaging = MessagingClient(redis_client)
        self._run_interval = 60  # Every 1 minute for demo

    async def run(self):
        logger.info(f"{self.name}: Starting deployment governance")

        while self.status == "running":
            try:
                await self._select_and_promote_paper_candidates()
                await self._evaluate_paper_strategies_for_promotion()
                await self._sweep_pending_deployments()
                await self._check_live_regressions()
            except Exception as e:
                logger.error(f"{self.name}: Governance sweep error: {e}")

            for _ in range(self._run_interval // 10):
                await self._sleep(10)
                if self.status != "running":
                    return

    async def _sleep(self, seconds: int):
        import asyncio

        await asyncio.sleep(seconds)

    async def propose_deployment(
        self,
        strategy_id: str,
        proposed_by: str,
        mode: str = "paper",
        metadata: Optional[dict] = None,
    ) -> str:
        """Propose a new deployment. Returns deployment_id."""
        dep_id = self.select_trace_id()
        await self.db._execute_insert(
            """
            INSERT INTO deployment_governance
                (id, strategy_id, mode, status, proposed_by,
                 proposed_at, metadata)
            VALUES
                (:id, :strategy_id, :mode, 'pending_approval',
                 :proposed_by, NOW(), CAST(:metadata AS jsonb))
            """,
            {
                "id": dep_id,
                "strategy_id": strategy_id,
                "mode": mode,
                "proposed_by": proposed_by,
                "metadata": json.dumps(metadata or {}),
            },
        )
        logger.info(
            f"{self.name}: Deployment proposed {dep_id} for {strategy_id} ({mode})"
        )
        return dep_id

    async def approve_deployment(
        self,
        deployment_id: str,
        approved_by: str,
    ) -> bool:
        """Approve a pending deployment."""
        async with self.db.engine.begin() as conn:
            r = await conn.execute(
                text("""
                    UPDATE deployment_governance
                    SET status = 'approved',
                        approved_by = :approved_by,
                        approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :id AND status = 'pending_approval'
                """),
                {"id": deployment_id, "approved_by": approved_by},
            )
            if r.rowcount == 0:
                logger.warning(
                    f"{self.name}: Cannot approve {deployment_id} — not pending"
                )
                return False

        logger.info(
            f"{self.name}: Deployment {deployment_id} approved by {approved_by}"
        )
        return True

    async def execute_deployment(self, deployment_id: str) -> bool:
        """Execute an approved deployment, moving it through modes."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT strategy_id, mode, metadata
                    FROM deployment_governance WHERE id = :id
                """),
                {"id": deployment_id},
            )
            row = r.fetchone()
            if not row:
                return False

            strategy_id = str(row[0])
            target_mode = str(row[1])
            meta_raw = row[2]

        # Run validation gate (lenient for paper mode)
        passed = await self._validate_deployment_gate(strategy_id, mode=target_mode)
        if not passed:
            await self._update_status(deployment_id, "rejected")
            logger.warning(
                f"{self.name}: Deployment {deployment_id} rejected — validation failed"
            )
            return False

        # Execute
        await self._update_status(deployment_id, "deploying")
        await self._update_strategy_mode(strategy_id, target_mode)
        await self._update_status(deployment_id, target_mode)

        # BRIDGE FIX: Publish 'validated' signal to Redis so ExecutionGateway acts immediately
        if target_mode in ("paper", "shadow", "live"):
            try:
                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {
                        "type": "validated",
                        "strategy_id": strategy_id,
                        "deployment_id": deployment_id,
                        "mode": target_mode,
                    },
                )
                logger.info(
                    f"{self.name}: Published activation signal for {strategy_id}"
                )
            except Exception as e:
                logger.warning(f"{self.name}: Failed to publish activation signal: {e}")

        logger.info(f"{self.name}: Deployment {deployment_id} active ({target_mode})")
        return True

    async def rollback_deployment(self, deployment_id: str) -> bool:
        """Rollback a deployment."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT strategy_id FROM deployment_governance WHERE id = :id
                """),
                {"id": deployment_id},
            )
            row = r.fetchone()
            if not row:
                return False
            strategy_id = str(row[0])

        await self._update_status(deployment_id, "rolling_back")
        await self._update_strategy_mode(strategy_id, "paper")
        await self._update_status(deployment_id, "rolled_back")

        logger.warning(f"{self.name}: Deployment {deployment_id} rolled back")
        return True

    async def _sweep_pending_deployments(self):
        """Auto-approve paper deployments, flag others for review."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT id, strategy_id, mode, proposed_at
                    FROM deployment_governance
                    WHERE status = 'pending_approval'
                    ORDER BY proposed_at ASC
                """),
            )
            pending = r.fetchall()

        for row in pending:
            dep_id = str(row[0])
            mode = str(row[2])
            if mode == "paper":
                await self.approve_deployment(dep_id, "DeploymentGovernor(auto)")
                await self.execute_deployment(dep_id)

    async def _select_and_promote_paper_candidates(self):
        """
        Phase 37B: Proactively select elite/validated strategies for paper trading
        using tournament selection. This provides exploration vs exploitation balance
        instead of always picking the highest-scoring strategy.
        """
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT s.id, s.name, b.composite_fitness_score AS composite_fitness, b.short_window_score,
                           b.sharpe, b.win_rate
                    FROM strategies s
                    JOIN backtest_results b ON b.strategy_id = s.id
                    WHERE s.status IN ('elite', 'validated')
                      AND b.composite_fitness_score > 0
                      AND NOT EXISTS (
                          SELECT 1 FROM deployment_governance d
                          WHERE d.strategy_id = s.id::text
                            AND d.status IN ('pending_approval', 'approved',
                                             'paper', 'shadow', 'partial_live', 'live')
                      )
                    ORDER BY b.composite_fitness_score DESC
                    LIMIT 50
                """),
            )
            rows = r.fetchall()

        if not rows:
            logger.debug(
                f"{self.name}: No elite/validated strategies available for promotion"
            )
            return

        # Convert to dicts for tournament selection
        candidates = []
        for row in rows:
            candidates.append(
                {
                    "id": str(row[0]),
                    "name": str(row[1] or ""),
                    "composite_fitness": float(row[2] or 0),
                    "short_window_score": float(row[3] or 0),
                    "sharpe": float(row[4] or 0),
                    "win_rate": float(row[5] or 0),
                }
            )

        # Tournament select 1 candidate for promotion (promotes diversity)
        selected = tournament_select_unique(
            candidates,
            tournament_size=5,
            key="composite_fitness",
            n_select=1,
            id_key="id",
        )

        if not selected:
            return

        winner = selected[0]
        logger.info(
            f"{self.name}: Tournament selected {winner['name']} "
            f"(fitness={winner['composite_fitness']:.1f}, "
            f"sharpe={winner['sharpe']:.2f}) for paper promotion"
        )

        await self.propose_deployment(
            strategy_id=winner["id"],
            proposed_by="DeploymentGovernor(tournament)",
            mode="paper",
            metadata={
                "selection_method": "tournament",
                "tournament_size": 5,
                "composite_fitness": winner["composite_fitness"],
                "short_window_score": winner["short_window_score"],
            },
        )

    async def _evaluate_paper_strategies_for_promotion(self):
        """
        Evaluate strategies currently in paper mode.
        If they meet high performance standards based on real paper trades,
        promote them to shadow or partial_live.
        """
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT 
                        d.id as deployment_id,
                        d.strategy_id,
                        sp.monthly_return_pct,
                        sp.sharpe_ratio,
                        sp.profit_factor,
                        sp.max_drawdown_pct,
                        sp.total_trades,
                        sp.win_rate
                    FROM deployment_governance d
                    JOIN strategy_performance sp ON d.strategy_id = sp.strategy_id::text
                    WHERE d.status = 'paper' 
                      AND sp.total_trades >= 5
                """)
            )
            candidates = r.fetchall()

        for row in candidates:
            d_dict = dict(row._mapping)
            dep_id = str(d_dict['deployment_id'])
            strategy_id = str(d_dict['strategy_id'])
            
            # Use 0 for missing metrics to penalize lack of data safely
            ret = float(d_dict.get('monthly_return_pct') or 0.0)
            sharpe = float(d_dict.get('sharpe_ratio') or 0.0)
            pf = float(d_dict.get('profit_factor') or 0.0)
            win_rate = float(d_dict.get('win_rate') or 0.0)
            # Expectancy approximation: PF is used, we can also use win_rate for proxy
            expectancy = pf * win_rate 
            dd = float(d_dict.get('max_drawdown_pct') or 0.0)
            
            # User-defined deployment score formula
            deployment_score = (0.30 * ret) + (0.25 * sharpe) + (0.20 * pf) + (0.15 * expectancy) - (0.10 * dd)
            
            # Minimum threshold for promotion
            if deployment_score > 5.0 and ret > 5.0:
                logger.info(
                    f"{self.name}: Strategy {strategy_id} passed paper threshold! "
                    f"Score: {deployment_score:.2f} (Ret:{ret:.1f}%, PF:{pf:.2f})"
                )
                # Promote to live (or shadow/partial_live)
                await self.propose_deployment(
                    strategy_id=strategy_id,
                    proposed_by="DeploymentGovernor(performance_promotion)",
                    mode="live",
                    metadata={
                        "selection_method": "performance_score",
                        "deployment_score": deployment_score,
                        "monthly_return_pct": ret,
                        "profit_factor": pf,
                    },
                )

    async def _check_live_regressions(self):
        """Check for performance regressions in live strategies."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT d.id, d.strategy_id, d.mode, d.activated_at
                    FROM deployment_governance d
                    WHERE d.status IN ('partial_live', 'live')
                      AND d.activated_at < NOW() - INTERVAL '1 hour'
                """),
            )
            live = r.fetchall()

        for row in live:
            dep_id = str(row[0])
            strategy_id = str(row[1])
            # Check for performance degradation
            has_regression = await self._detect_regression(strategy_id)
            if has_regression:
                logger.warning(
                    f"{self.name}: Regression detected in {strategy_id}, auto-rolling back"
                )
                await self.rollback_deployment(dep_id)

    # Deployment gate thresholds by mode
    # Progressive: paper (lenient) → shadow → partial_live → live (strict)
    # UNIT FIX (Sprint 1B): walk_forward_score is a FRACTION in [0, 1] (fraction
    # of windows survived), as persisted by WalkForwardAnalyzer. The previous
    # 30.0/40.0/50.0 thresholds were on a 0–100 scale and therefore unreachable
    # (observed max ~0.80), silently disabling the gate. Restated on [0, 1] to
    # match the Sprint 1B calibration→spec band (overfit/regime/monte_carlo were
    # already correct fractions).
    GATE_THRESHOLDS = {
        "paper": {
            "min_walk_forward_score": 0.0,
            "max_overfit_probability": 1.0,
            "min_regime_survival": 0.0,
            "min_monte_carlo_survival": 0.0,
        },
        "shadow": {
            "min_walk_forward_score": 0.30,  # was 30.0 (unit bug); >=30% windows
            "max_overfit_probability": 0.7,
            "min_regime_survival": 0.2,  # At least 1/5 regimes
            "min_monte_carlo_survival": 0.3,  # 30% sims positive
        },
        "partial_live": {
            "min_walk_forward_score": 0.45,  # was 40.0 (unit bug)
            "max_overfit_probability": 0.6,
            "min_regime_survival": 0.4,  # At least 2/5 regimes
            "min_monte_carlo_survival": 0.5,  # 50% sims positive
        },
        "live": {
            "min_walk_forward_score": 0.60,  # was 50.0 (unit bug); spec >=60% windows
            "max_overfit_probability": 0.5,
            "min_regime_survival": 0.6,  # At least 3/5 regimes
            "min_monte_carlo_survival": 0.7,  # 70% sims positive
        },
    }

    async def _validate_deployment_gate(
        self, strategy_id: str, mode: str = "paper"
    ) -> bool:
        """
        Validate that a strategy is fit for deployment using real data from
        the advanced validation tables (walk_forward_analysis, overfitting_analysis,
        regime_validation, monte_carlo_analysis).

        These tables are now populated by BacktestRunner._run_advanced_validation()
        after each backtest completes, so data SHOULD exist for every backtested strategy.

        Returns False (rejects deployment) if:
        - Required analysis tables are missing
        - No analysis data exists for this strategy
        - Any metric fails its mode-specific threshold
        """
        thresholds = self.GATE_THRESHOLDS.get(mode, self.GATE_THRESHOLDS["paper"])

        try:
            async with self.db.engine.connect() as conn:
                r = await conn.execute(
                    text("""
                        SELECT
                            COALESCE((
                                SELECT walk_forward_score
                                FROM walk_forward_analysis
                                WHERE strategy_id = :sid
                                ORDER BY analyzed_at DESC LIMIT 1
                            ), 0) AS wf_score,
                            COALESCE((
                                SELECT overfit_probability
                                FROM overfitting_analysis
                                WHERE strategy_id = :sid
                                ORDER BY analyzed_at DESC LIMIT 1
                            ), 1.0) AS overfit_prob,
                            COALESCE((
                                SELECT regime_survival_score
                                FROM regime_validation
                                WHERE strategy_id = :sid
                                ORDER BY validated_at DESC LIMIT 1
                            ), 0.0) AS regime_survival,
                            COALESCE((
                                SELECT monte_carlo_survival_score
                                FROM monte_carlo_analysis
                                WHERE strategy_id = :sid
                                ORDER BY simulated_at DESC LIMIT 1
                            ), 0.0) AS mc_survival
                    """),
                    {"sid": strategy_id},
                )
                row = r.fetchone()
        except ProgrammingError:
            logger.warning(
                f"{self.name}: Analysis tables missing — rejecting {mode} deployment for {strategy_id}"
            )
            return False
        except Exception as e:
            logger.warning(f"{self.name}: Gate query failed for {strategy_id}: {e}")
            return False

        if not row:
            logger.warning(
                f"{self.name}: No analysis data for {strategy_id} — rejecting {mode} deployment"
            )
            return False

        wf_score = float(row[0] or 0)
        overfit_prob = float(row[1] or 1.0)
        regime_survival = float(row[2] or 0.0)
        mc_survival = float(row[3] or 0.0)

        # Check all thresholds
        failures = []
        if wf_score < thresholds["min_walk_forward_score"]:
            failures.append(
                f"walk_forward {wf_score:.2f} < {thresholds['min_walk_forward_score']}"
            )
        if overfit_prob >= thresholds["max_overfit_probability"]:
            failures.append(
                f"overfit_prob {overfit_prob:.2f} >= {thresholds['max_overfit_probability']}"
            )
        if regime_survival < thresholds["min_regime_survival"]:
            failures.append(
                f"regime_survival {regime_survival:.2f} < {thresholds['min_regime_survival']}"
            )
        if mc_survival < thresholds["min_monte_carlo_survival"]:
            failures.append(
                f"mc_survival {mc_survival:.2f} < {thresholds['min_monte_carlo_survival']}"
            )

        if failures:
            logger.info(
                f"{self.name}: {mode} deployment gate FAILED for {strategy_id}: "
                f"{' | '.join(failures)}"
            )
            return False

        logger.info(
            f"{self.name}: {mode} deployment gate PASSED for {strategy_id}: "
            f"wf={wf_score:.2f} overfit={overfit_prob:.2f} "
            f"regime={regime_survival:.2f} mc={mc_survival:.2f}"
        )
        return True

    async def _detect_regression(self, strategy_id: str) -> bool:
        """
        Check if a strategy has regressed compared to backtest.

        Uses multi-dimensional regression detection from the advanced
        validation tables (walk_forward_analysis, overfitting_analysis,
        regime_validation, monte_carlo_analysis). A strategy is flagged
        as regressed if 2+ of 4 metrics signal degradation.
        """
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT
                        COALESCE((
                            SELECT walk_forward_score
                            FROM walk_forward_analysis
                            WHERE strategy_id = :sid
                            ORDER BY analyzed_at DESC LIMIT 1
                        ), 0) AS wf_score,
                        COALESCE((
                            SELECT overfit_probability
                            FROM overfitting_analysis
                            WHERE strategy_id = :sid
                            ORDER BY analyzed_at DESC LIMIT 1
                        ), 1.0) AS overfit_prob,
                        COALESCE((
                            SELECT regime_survival_score
                            FROM regime_validation
                            WHERE strategy_id = :sid
                            ORDER BY validated_at DESC LIMIT 1
                        ), 0.0) AS regime_survival,
                        COALESCE((
                            SELECT monte_carlo_survival_score
                            FROM monte_carlo_analysis
                            WHERE strategy_id = :sid
                            ORDER BY simulated_at DESC LIMIT 1
                        ), 0.0) AS mc_survival
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            if not row:
                return False

            wf_score = float(row[0] or 0)
            overfit_prob = float(row[1] or 1.0)
            regime_survival = float(row[2] or 0.0)
            mc_survival = float(row[3] or 0.0)

            # Count regression signals across 4 dimensions
            regression_signals = 0

            if wf_score < 20.0:
                regression_signals += 1
            if overfit_prob > 0.6:
                regression_signals += 1
            if regime_survival < 0.2:
                regression_signals += 1
            if mc_survival < 0.3:
                regression_signals += 1

            # Flag if 2+ of 4 metrics indicate degradation
            is_regressed = regression_signals >= 2

            if is_regressed:
                logger.warning(
                    f"{self.name}: Regression detected for {strategy_id}: "
                    f"wf={wf_score:.2f} overfit={overfit_prob:.2f} "
                    f"regime={regime_survival:.2f} mc={mc_survival:.2f} "
                    f"signals={regression_signals}/4"
                )

            return is_regressed

    async def _update_status(self, deployment_id: str, status: str):
        await self.db._execute_insert(
            """
            UPDATE deployment_governance
            SET status = :status,
                activated_at = CASE WHEN :status IN ('paper','shadow','partial_live','live')
                                    THEN NOW() ELSE activated_at END,
                updated_at = NOW()
            WHERE id = :id
            """,
            params={"id": deployment_id, "status": status},
        )

    async def _update_strategy_mode(self, strategy_id: str, mode: str):
        await self.db._execute_insert(
            """
            UPDATE strategies
            SET deployment_mode = :mode
            WHERE id = :sid
            """,
            params={"sid": strategy_id, "mode": mode},
        )

    async def get_deployment_report(self) -> dict:
        """Get current deployment status overview."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT status, COUNT(*) as cnt
                    FROM deployment_governance
                    GROUP BY status ORDER BY cnt DESC
                """)
            )
            by_status = {str(row[0]): row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("""
                    SELECT id, strategy_id, mode, status, proposed_by,
                           approved_by, proposed_at, activated_at
                    FROM deployment_governance
                    ORDER BY proposed_at DESC LIMIT 20
                """)
            )
            recent = []
            for row in r.fetchall():
                recent.append(
                    {
                        "id": str(row[0]),
                        "strategy_id": str(row[1]),
                        "mode": str(row[2]),
                        "status": str(row[3]),
                        "proposed_by": str(row[4]),
                        "approved_by": str(row[5]) if row[5] else None,
                        "proposed_at": row[6].isoformat()
                        if row[6] and hasattr(row[6], "isoformat")
                        else str(row[6])
                        if row[6]
                        else None,
                        "activated_at": row[7].isoformat()
                        if row[7] and hasattr(row[7], "isoformat")
                        else str(row[7])
                        if row[7]
                        else None,
                    }
                )

            return {
                "by_status": by_status,
                "recent_deployments": recent,
            }
