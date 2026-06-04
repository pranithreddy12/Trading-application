"""dominant_organism_tracker.py — Phase 31A: Dominant Organism Tracking.

Purpose:
Identifies and tracks persistent competitive advantages across the organism population.
Tracks:
  - Longest surviving organisms (lifespan in cycles/bars)
  - Highest capital-efficiency organisms (score/drawdown)
  - Highest expectancy organisms (average win/loss ratio over lifetime)
  - Best regime specialists (regime-conditioned survivability)
  - Most resilient mutation families (family-level survival rates)
  - Organism lifespan, survival scores, retirement causes, recovery ability

Outputs persisted to dominant_organism_log and consumed by:
  - PortfolioEvolutionPressure (capital concentration toward dominants)
  - StrategyRetirementEngine (override retirement for dominants)
  - MutationLineageTracker (which lineages produce dominants)
"""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class DominantOrganismTracker(BaseAgent):
    """L7 Meta Agent — Tracks and identifies dominant organisms over time."""

    name = "DominantOrganismTracker"
    agent_type = "dominant_organism_tracker"
    layer = "L7"

    def __init__(self, redis_client=None, db_client=None, run_interval: int = 1800):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.run_interval = run_interval

        # Dominance thresholds
        self.SURVIVAL_TOP_PCT = 0.25        # Top 25% by lifespan = dominant
        self.CAPITAL_EFFICIENCY_MIN = 2.0    # Score/drawdown ratio minimum for dominance
        self.EXPECTANCY_MIN = 0.15           # Minimum expectancy for dominant status
        self.MIN_TRADES_DOMINANT = 10        # Minimum trades to be considered

        # Recovery scoring
        self.RECOVERY_WINDOW_CYCLES = 5      # How many cycles to evaluate recovery
        self.DRAWDOWN_RECOVERY_THRESHOLD = 0.5  # Recovered if drawdown halved

        self._dominant_cache: dict = {}
        self._lineage_leaderboard: list = []

    async def run(self):
        logger.info(f"{self.name}: starting dominant organism tracking (every {self.run_interval}s)")
        while self.status == "running":
            try:
                await self._tracking_cycle()
            except Exception as e:
                logger.error(f"{self.name}: tracking cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _tracking_cycle(self):
        """Full tracking cycle: collect data, compute dominance, persist."""
        organisms = await self._fetch_all_organisms()
        if not organisms or len(organisms) < 2:
            logger.info(f"{self.name}: insufficient organisms for dominance tracking ({len(organisms) if organisms else 0})")
            return

        # 1. Compute lifespan rankings
        lifespan_rankings = self._rank_by_lifespan(organisms)

        # 2. Compute capital efficiency rankings
        efficiency_rankings = self._rank_by_capital_efficiency(organisms)

        # 3. Compute expectancy rankings
        expectancy_rankings = self._rank_by_expectancy(organisms)

        # 4. Compute regime specialization rankings
        regime_specialists = self._rank_by_regime_specialization(organisms)

        # 5. Compute mutation family resilience
        family_resilience = await self._compute_mutation_family_resilience()

        # 6. Identify dominant organisms across all metrics
        dominant_organisms = self._identify_dominants(
            organisms, lifespan_rankings, efficiency_rankings,
            expectancy_rankings, regime_specialists
        )

        # 7. Compute recovery ability for degraded/quarantined organisms
        recovery_scores = self._compute_recovery_scores(organisms)

        # 8. Compute retirement cause distribution
        retirement_causes = await self._fetch_retirement_causes()

        # Build tracking record
        tracking = {
            "id": str(uuid.uuid4()),
            "tracked_at": datetime.now(timezone.utc),
            "n_organisms_total": len(organisms),
            "n_dominant_identified": len(dominant_organisms),
            "dominant_organisms": dominant_organisms,
            "lifespan_rankings": lifespan_rankings[:10],
            "efficiency_rankings": efficiency_rankings[:10],
            "expectancy_rankings": expectancy_rankings[:10],
            "regime_specialists": regime_specialists,
            "mutation_family_resilience": family_resilience,
            "recovery_scores": recovery_scores[:10],
            "retirement_cause_distribution": retirement_causes,
            "ecosystem_health": {
                "n_surviving_organisms": len([o for o in organisms if o.get("status") in ("validated", "elite", "live", "promoted", "dominant")]),
                "n_degraded": len([o for o in organisms if o.get("lifecycle_state") in ("degrading", "quarantined")]),
                "n_retired": len([o for o in organisms if o.get("lifecycle_state") == "retired"]),
                "avg_lifespan_bars": float(np.mean([o.get("age_bars", 0) or 0 for o in organisms])),
                "dominant_concentration": round(len(dominant_organisms) / max(1, len(organisms)), 4),
            },
        }

        # Persist
        await self._persist_tracking(tracking)
        self._dominant_cache = {d["strategy_id"]: d for d in dominant_organisms}

        logger.info(
            f"{self.name}: Tracked {len(organisms)} organisms, "
            f"{len(dominant_organisms)} dominant identified"
        )

    async def _fetch_all_organisms(self) -> list[dict]:
        """Fetch all strategies with full lifecycle and performance data."""
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        s.id, s.name, s.status, s.lifecycle_state, s.age_bars,
                        s.author_agent, s.created_at,
                        b.composite_fitness_score, b.sharpe, b.win_rate,
                        b.total_trades, b.max_drawdown, b.sortino_ratio,
                        b.short_window_score,
                        b.results,
                        b.cagr, b.expectancy
                    FROM strategies s
                    LEFT JOIN LATERAL (
                        SELECT composite_fitness_score, sharpe, win_rate,
                               total_trades, max_drawdown, sortino_ratio,
                               short_window_score, results, cagr, expectancy
                        FROM backtest_results
                        WHERE strategy_id = s.id
                        ORDER BY created_at DESC LIMIT 1
                    ) b ON TRUE
                    ORDER BY s.created_at DESC
                    LIMIT 200
                """))
                rows = result.fetchall()

                # Group trades per strategy for recovery scoring
                trade_map = defaultdict(list)
                try:
                    trade_result = await conn.execute(text("""
                        SELECT strategy_id, COUNT(*) as trade_count,
                               COALESCE(SUM(pnl), 0) as total_pnl,
                               COALESCE(AVG(pnl_pct), 0) as avg_pnl_pct
                        FROM backtest_trades
                        WHERE strategy_id IN (SELECT id FROM strategies)
                        GROUP BY strategy_id
                        ORDER BY trade_count DESC
                        LIMIT 5000
                    """))
                    for tr in trade_result.fetchall():
                        trade_map[str(tr[0])].append({
                            "trade_count": int(tr[1] or 0),
                            "total_pnl": float(tr[2] or 0),
                            "avg_pnl_pct": float(tr[3] or 0),
                        })
                except Exception:
                    pass

                out = []
                for r in rows:
                    sid = str(r[0])
                    results_raw = r[14]
                    if results_raw is None:
                        results_raw = {}
                    elif isinstance(results_raw, str):
                        try:
                            results_raw = json.loads(results_raw)
                        except Exception:
                            results_raw = {}

                    trades = trade_map.get(sid, [])

                    out.append({
                        "id": sid,
                        "name": r[1],
                        "status": r[2],
                        "lifecycle_state": r[3] or "emerging",
                        "age_bars": int(r[4] or 0),
                        "author_agent": r[5],
                        "created_at": r[6],
                        "composite_fitness_score": float(r[7] or 0),
                        "sharpe": float(r[8] or 0),
                        "win_rate": float(r[9] or 0),
                        "total_trades": int(r[10] or 0),
                        "max_drawdown": float(r[11] or 0),
                        "profit_factor": float(results_raw.get("profit_factor", 1.0)),
                        "holdout_sharpe": float(r[8] or 0),
                        "short_window_score": float(r[13] or 0),
                        "entry_count": 0,
                        "cagr": float(r[15] or 0),
                        "avg_return_pct": float(results_raw.get("avg_return_pct", results_raw.get("mean_return_pct", 0))),
                        "total_return": float(results_raw.get("total_return", 0)),
                        "sortino": float(r[12] or 0),
                        "expectancy": float(r[16] or 0),
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch organisms failed: {e}")
            return []

    def _rank_by_lifespan(self, organisms: list[dict]) -> list[dict]:
        """Rank organisms by age_bars (lifespan in trading bars)."""
        scored = []
        for o in organisms:
            lifespan = max(o.get("age_bars", 0), 0)
            scored.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "lifespan_bars": lifespan,
                "status": o.get("lifecycle_state", o.get("status", "unknown")),
            })
        scored.sort(key=lambda x: -x["lifespan_bars"])
        return scored

    def _rank_by_capital_efficiency(self, organisms: list[dict]) -> list[dict]:
        """Rank by composite_fitness_score / max_drawdown ratio."""
        scored = []
        for o in organisms:
            score = o.get("composite_fitness_score", 0)
            dd = max(abs(o.get("max_drawdown", 0.01)), 0.01)
            efficiency = score / dd if dd > 0 else 0
            scored.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "efficiency": round(efficiency, 4),
                "composite_score": round(score, 2),
                "max_drawdown": round(o.get("max_drawdown", 0), 4),
                "total_trades": o.get("total_trades", 0),
            })
        scored.sort(key=lambda x: -x["efficiency"])
        return scored

    def _rank_by_expectancy(self, organisms: list[dict]) -> list[dict]:
        """Rank by expectancy (average win/loss ratio)."""
        scored = []
        for o in organisms:
            expectancy = o.get("expectancy", 0)
            win_rate = o.get("win_rate", 0.5)
            avg_return = o.get("avg_return_pct", 0)

            # Composite expectancy signal
            composite_exp = (
                expectancy * 0.4
                + (win_rate - 0.5) * 0.3
                + avg_return * 10 * 0.3
            )
            scored.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "expectancy": round(expectancy, 4),
                "composite_expectancy_score": round(composite_exp, 4),
                "win_rate": round(win_rate, 4),
                "avg_return_pct": round(avg_return, 6),
                "total_trades": o.get("total_trades", 0),
            })
        scored.sort(key=lambda x: -x["composite_expectancy_score"])
        return scored

    def _rank_by_regime_specialization(self, organisms: list[dict]) -> list[dict]:
        """Identify organisms that show regime-specific strength.
        Uses proxy: high sharpe + low drawdown = likely regime-adapted."""
        specialists = []
        for o in organisms:
            sharpe = o.get("sharpe", 0) or o.get("holdout_sharpe", 0)
            dd = abs(o.get("max_drawdown", 0))
            trades = o.get("total_trades", 0)

            if trades < self.MIN_TRADES_DOMINANT:
                continue

            # A specialist has high risk-adjusted return and low drawdown
            specialization_score = (max(0, sharpe) * 10) / max(dd, 0.01)
            specializations = []

            if sharpe > 1.0 and dd < 15:
                specializations.append("bull_market")
            if sharpe > 0.5 and dd < 10:
                specializations.append("low_vol")
            if trades > 50 and sharpe > 0.3:
                specializations.append("high_liquidity")
            if dd > 20 and sharpe > 0.5:
                specializations.append("vol_tolerant")

            if specializations:
                specialists.append({
                    "strategy_id": o["id"],
                    "strategy_name": o["name"],
                    "specialization_score": round(specialization_score, 4),
                    "specializations": specializations,
                    "sharpe": round(sharpe, 2),
                    "max_drawdown": round(dd, 2),
                    "total_trades": trades,
                })

        specialists.sort(key=lambda x: -x["specialization_score"])
        return specialists[:15]

    async def _compute_mutation_family_resilience(self) -> list[dict]:
        """Compute survival rates per mutation family.

        Uses CTE to avoid Postgres GROUP BY restriction on correlated subqueries
        inside aggregate FILTER clauses.
        """
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    WITH latest_fitness AS (
                        SELECT DISTINCT ON (br.strategy_id)
                            br.strategy_id,
                            br.composite_fitness_score
                        FROM backtest_results br
                        ORDER BY br.strategy_id, br.created_at DESC
                    )
                    SELECT
                        m.mutation_type,
                        COUNT(*) AS total_applications,
                        COUNT(*) FILTER (
                            WHERE lf.composite_fitness_score > 30
                        ) AS survived_count,
                        COALESCE(AVG(lf.composite_fitness_score), 0) AS avg_fitness
                    FROM mutation_memory m
                    LEFT JOIN latest_fitness lf
                        ON lf.strategy_id = m.child_strategy_id
                    WHERE m.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY m.mutation_type
                    ORDER BY survived_count DESC
                    LIMIT 20
                """))
                rows = result.fetchall()
                out = []
                for r in rows:
                    total = int(r[1] or 0)
                    survived = int(r[2] or 0)
                    out.append({
                        "mutation_type": str(r[0]),
                        "total_applications": total,
                        "survived_count": survived,
                        "survival_rate": round(survived / max(1, total), 4),
                        "avg_fitness_contribution": round(float(r[3] or 0), 2),
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: mutation family resilience failed: {e}")
            return []

    def _identify_dominants(
        self, organisms: list[dict],
        lifespan_ranks: list[dict],
        efficiency_ranks: list[dict],
        expectancy_ranks: list[dict],
        regime_specialists: list[dict],
    ) -> list[dict]:
        """Cross-reference all rankings to identify dominant organisms."""
        # Build lookup sets
        top_lifespan = {r["strategy_id"] for r in lifespan_ranks[:max(3, int(len(lifespan_ranks) * self.SURVIVAL_TOP_PCT))]}
        top_efficiency = {r["strategy_id"] for r in efficiency_ranks[:max(3, int(len(efficiency_ranks) * self.SURVIVAL_TOP_PCT))]}
        top_expectancy = {r["strategy_id"] for r in expectancy_ranks[:max(3, int(len(expectancy_ranks) * self.SURVIVAL_TOP_PCT))]}
        specialist_ids = {r["strategy_id"] for r in regime_specialists}

        organism_map = {o["id"]: o for o in organisms}
        efficiency_map = {r["strategy_id"]: r for r in efficiency_ranks}
        expectancy_map = {r["strategy_id"]: r for r in expectancy_ranks}
        lifespan_map = {r["strategy_id"]: r for r in lifespan_ranks}
        specialist_map = {r["strategy_id"]: r for r in regime_specialists}

        dominants = []
        for sid in (top_lifespan | top_efficiency | top_expectancy | specialist_ids):
            o = organism_map.get(sid)
            if not o:
                continue

            categories = []
            score = 0

            if sid in top_lifespan:
                categories.append("longevity")
                score += 25
            if sid in top_efficiency:
                categories.append("capital_efficiency")
                score += 30
            if sid in top_expectancy:
                categories.append("expectancy")
                score += 25
            if sid in specialist_ids:
                categories.append("regime_specialist")
                score += 20

            # Bonus for multi-category dominants
            if len(categories) >= 2:
                score += 15
            if len(categories) >= 3:
                score += 10

            dominants.append({
                "strategy_id": sid,
                "strategy_name": o.get("name", ""),
                "dominance_score": score,
                "dominance_categories": categories,
                "lifespan_bars": lifespan_map.get(sid, {}).get("lifespan_bars", 0),
                "efficiency": efficiency_map.get(sid, {}).get("efficiency", 0),
                "composite_expectancy": expectancy_map.get(sid, {}).get("composite_expectancy_score", 0),
                "specialization_score": specialist_map.get(sid, {}).get("specialization_score", 0),
                "specializations": specialist_map.get(sid, {}).get("specializations", []),
                "status": o.get("lifecycle_state", o.get("status", "unknown")),
            })

        dominants.sort(key=lambda x: -x["dominance_score"])
        return dominants

    def _compute_recovery_scores(self, organisms: list[dict]) -> list[dict]:
        """Compute drawdown recovery ability scores for struggling organisms."""
        recovery_scores = []
        for o in organisms:
            # Check lifecycle or status for struggling organisms
            lifecycle = o.get("lifecycle_state", "") or ""
            status = o.get("status", "") or ""
            if lifecycle not in ("retired", "degrading", "quarantined") and status not in ("code_failed", "backtest_failed", "validation_failed", "retired"):
                # Still check if organism has poor enough metrics to warrant recovery tracking
                if o.get("composite_fitness_score", 50) > 30:
                    continue
            dd = abs(o.get("max_drawdown", 0))
            score = o.get("composite_fitness_score", 0)
            trades = o.get("total_trades", 0)

            # Recovery potential = (current score) / (max drawdown * trades)
            recovery = score / max(1, dd * max(1, trades / 10))
            recovery_scores.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "recovery_potential": round(recovery, 4),
                "current_state": o.get("lifecycle_state"),
                "max_drawdown": round(dd, 2),
                "current_score": round(score, 2),
                "total_trades": trades,
            })

        recovery_scores.sort(key=lambda x: -x["recovery_potential"])
        return recovery_scores

    async def _fetch_retirement_causes(self) -> dict:
        """Fetch distribution of retirement causes."""
        if not self.db:
            return {}
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT lifecycle_state, COUNT(*) AS cnt
                    FROM strategies
                    WHERE lifecycle_state IN ('retired', 'quarantined', 'degrading')
                    GROUP BY lifecycle_state
                """))
                rows = result.fetchall()
                return {str(r[0]): int(r[1]) for r in rows} if rows else {}
        except Exception:
            return {}

    async def _persist_tracking(self, tracking: dict):
        """Persist dominant organism tracking to dominant_organism_log table."""
        if not self.db:
            return
        try:
            await self.db._execute_insert("""
                INSERT INTO dominant_organism_log
                    (id, tracked_at, n_organisms_total, n_dominant_identified,
                     dominant_organisms, lifespan_rankings, efficiency_rankings,
                     expectancy_rankings, regime_specialists,
                     mutation_family_resilience, recovery_scores,
                     retirement_cause_distribution, ecosystem_health,
                     metadata)
                VALUES
                    (:id, :tracked_at, :n_organisms_total, :n_dominant_identified,
                     :dominant_organisms, :lifespan_rankings, :efficiency_rankings,
                     :expectancy_rankings, :regime_specialists,
                     :mutation_family_resilience, :recovery_scores,
                     :retirement_cause_distribution, :ecosystem_health,
                     :metadata)
            """, {
                "id": tracking["id"],
                "tracked_at": tracking["tracked_at"],
                "n_organisms_total": tracking["n_organisms_total"],
                "n_dominant_identified": tracking["n_dominant_identified"],
                "dominant_organisms": json.dumps(tracking["dominant_organisms"]),
                "lifespan_rankings": json.dumps(tracking["lifespan_rankings"]),
                "efficiency_rankings": json.dumps(tracking["efficiency_rankings"]),
                "expectancy_rankings": json.dumps(tracking["expectancy_rankings"]),
                "regime_specialists": json.dumps(tracking["regime_specialists"]),
                "mutation_family_resilience": json.dumps(tracking["mutation_family_resilience"]),
                "recovery_scores": json.dumps(tracking["recovery_scores"]),
                "retirement_cause_distribution": json.dumps(tracking["retirement_cause_distribution"]),
                "ecosystem_health": json.dumps(tracking["ecosystem_health"]),
                "metadata": json.dumps({"method": "multi_metric_cross_reference"}),
            })
        except Exception as e:
            logger.warning(f"{self.name}: persist failed: {e}")

    async def get_dominant_organisms(self) -> list[dict]:
        """Public method: return current dominant organisms."""
        return list(self._dominant_cache.values())

    async def is_dominant(self, strategy_id: str) -> bool:
        """Public method: check if a strategy is dominant."""
        return strategy_id in self._dominant_cache
