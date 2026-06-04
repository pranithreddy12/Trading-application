"""portfolio_evolution_pressure.py — Phase 31E: Portfolio Evolution Pressure.

Purpose:
Forces adaptive allocation behavior at the portfolio level:
  - Dynamically reduce allocation to weak organisms
  - Increase capital to dominant organisms
  - Penalize correlated organism clusters
  - Reward diversification under stress
  - Enforce adaptive capital migration

Goal:
Portfolio layer becomes evolutionarily selective, concentrating capital
toward dominant organisms and starving weak ones.

Outputs persisted to portfolio_evolution_log and consumed by:
  - CapitalAllocator (override weights)
  - StrategyRetirementEngine (accelerate weak organism retirement)
  - DominantOrganismTracker (capital concentration feedback)
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


class PortfolioEvolutionPressure(BaseAgent):
    """L6 Meta Agent — Evolutionary portfolio pressure."""

    name = "PortfolioEvolutionPressure"
    agent_type = "portfolio_evolution"
    layer = "L6"

    def __init__(self, redis_client=None, db_client=None, run_interval: int = 1800):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.run_interval = run_interval

        # Evolution pressure thresholds
        self.WEAK_ORGANISM_THRESHOLD = 20.0     # Score below this = weak
        self.DOMINANT_BOOST_MULTIPLIER = 1.5     # Boost dominant allocation by 50%
        self.CORRELATION_PENALTY = 0.5            # 50% reduction for correlated clusters
        self.DIVERSIFICATION_REWARD = 1.2         # 20% boost for diversity
        self.STRESS_DIVERSIFICATION_BOOST = 1.5   # 50% extra diversification reward under stress
        self.MIN_ALLOCATION_WEAK = 0.02           # Minimum allocation for weak organisms (2%)
        self.MAX_ALLOCATION_DOMINANT = 0.25       # Maximum allocation for dominant organisms

        self._latest_pressure: dict = {}

    async def run(self):
        logger.info(f"{self.name}: starting portfolio evolution pressure (every {self.run_interval}s)")
        while self.status == "running":
            try:
                await self._pressure_cycle()
            except Exception as e:
                logger.error(f"{self.name}: pressure cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _pressure_cycle(self):
        """Full evolution pressure cycle."""
        # 1. Fetch current portfolio state
        portfolio = await self._fetch_portfolio_state()
        if not portfolio or len(portfolio) < 3:
            logger.info(f"{self.name}: insufficient portfolio organisms ({len(portfolio) if portfolio else 0})")
            return

        # 2. Fetch dominant organisms from tracker (via DB)
        dominant_ids = await self._fetch_dominant_organism_ids()

        # 3. Fetch regime stress state
        stress_active = await self._fetch_stress_active()

        # 4. Compute organism strength scores
        strength_scores = self._compute_organism_strength(portfolio)

        # 5. Compute correlation penalties
        correlation_penalties = self._compute_correlation_penalties(portfolio)

        # 6. Compute diversification rewards
        diversification_rewards = self._compute_diversification_rewards(portfolio, stress_active)

        # 7. Apply evolution pressure to allocations
        pressured_allocations = self._apply_evolution_pressure(
            portfolio, strength_scores, dominant_ids,
            correlation_penalties, diversification_rewards
        )

        # 8. Compute capital migration signals
        migration_signals = self._compute_migration_signals(pressured_allocations)

        pressure = {
            "id": str(uuid.uuid4()),
            "computed_at": datetime.now(timezone.utc),
            "n_organisms_analyzed": len(portfolio),
            "n_dominant_organisms": len(dominant_ids),
            "stress_active": stress_active,
            "organism_strength_scores": strength_scores,
            "correlation_penalties": correlation_penalties,
            "diversification_rewards": diversification_rewards,
            "pressured_allocations": pressured_allocations,
            "migration_signals": migration_signals,
            "evolution_pressure_stats": {
                # Count adjustments more sensitively (>=1% change) so selection pressure is visible
                "n_weak_penalized": sum(1 for a in pressured_allocations if a.get("evolution_adjustment", 0) < -0.01),
                "n_dominant_boosted": sum(1 for a in pressured_allocations if a.get("evolution_adjustment", 0) > 0.01),
                "n_correlated_penalized": len(correlation_penalties),
                "total_capital_migrated": round(sum(abs(a.get("evolution_adjustment", 0)) for a in pressured_allocations) / 2, 4),
                "stress_diversification_active": stress_active,
            },
        }

        # Persist
        await self._persist_pressure(pressure)
        self._latest_pressure = pressure

        logger.info(
            f"{self.name}: Applied evolution pressure — "
            f"{pressure['evolution_pressure_stats']['n_dominant_boosted']} boosted, "
            f"{pressure['evolution_pressure_stats']['n_weak_penalized']} penalized, "
            f"migrated {pressure['evolution_pressure_stats']['total_capital_migrated']:.2%} of capital"
        )

    async def _fetch_portfolio_state(self) -> list[dict]:
        """Fetch current portfolio state from capital_allocation."""
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        s.id, s.name, s.status, s.lifecycle_state,
                        COALESCE(b.composite_fitness_score, 0) AS score,
                        COALESCE(b.sharpe, 0) AS sharpe,
                        COALESCE(b.win_rate, 0) AS win_rate,
                        COALESCE(b.total_trades, 0) AS total_trades,
                        COALESCE(b.max_drawdown, 0) AS max_drawdown,
                        COALESCE(ca.weight, 0) AS current_weight,
                        s.normalized_strategy
                    FROM strategies s
                    LEFT JOIN LATERAL (
                        SELECT * FROM backtest_results
                        WHERE strategy_id = s.id
                        ORDER BY created_at DESC LIMIT 1
                    ) b ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT weight FROM capital_allocation ca,
                        LATERAL jsonb_to_recordset(ca.final_allocations) AS fa(strategy_id text, weight float)
                        WHERE fa.strategy_id::uuid = s.id
                        ORDER BY ca.computed_at DESC LIMIT 1
                    ) ca ON TRUE
                    WHERE s.status IN ('validated', 'elite', 'promoted', 'live', 'research_candidate')
                    ORDER BY ca.weight DESC NULLS LAST
                    LIMIT 50
                """))
                rows = result.fetchall()
                out = []
                for r in rows:
                    ns_raw = r[10]
                    if isinstance(ns_raw, str):
                        try:
                            ns_raw = json.loads(ns_raw)
                        except Exception:
                            ns_raw = {}
                    out.append({
                        "id": str(r[0]),
                        "name": r[1],
                        "status": r[2],
                        "lifecycle_state": r[3] or "active",
                        "score": float(r[4] or 0),
                        "sharpe": float(r[5] or 0),
                        "win_rate": float(r[6] or 0),
                        "total_trades": int(r[7] or 0),
                        "max_drawdown": float(r[8] or 0),
                        "current_weight": float(r[9] or 0),
                        "archetype": (ns_raw.get("tags") or ["unknown"])[0] if isinstance(ns_raw, dict) else "unknown",
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch portfolio failed: {e}")
            return []

    async def _fetch_dominant_organism_ids(self) -> set:
        """Fetch dominant organism IDs from dominant_organism_log."""
        if not self.db:
            return set()
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT dominant_organisms
                    FROM dominant_organism_log
                    ORDER BY tracked_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                if row and row[0]:
                    doms = row[0]
                    if isinstance(doms, str):
                        doms = json.loads(doms)
                    return {d.get("strategy_id") for d in doms if isinstance(d, dict)}
        except Exception:
            pass
        return set()

    async def _fetch_stress_active(self) -> bool:
        """Check if regime stress perturbations are active."""
        if not self.db:
            return False
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM regime_perturbation_events
                    WHERE status = 'active'
                """))
                row = result.fetchone()
                return int(row[0] or 0) > 0 if row else False
        except Exception:
            return False

    def _compute_organism_strength(self, portfolio: list[dict]) -> list[dict]:
        """Compute strength scores for each organism."""
        # Compute raw multi-factor strength first
        scores = []
        for o in portfolio:
            score = o.get("score", 0)
            sharpe = o.get("sharpe", 0)
            win_rate = o.get("win_rate", 0.5)
            dd = abs(o.get("max_drawdown", 0.01))

            strength = (
                min(1.0, score / 100) * 0.30
                + max(0, min(1.0, sharpe / 3)) * 0.25
                + win_rate * 0.20
                + (1.0 - min(1.0, dd / 30)) * 0.25
            )

            scores.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "strength_score": round(strength, 4),
                "current_weight": o.get("current_weight", 0),
            })

        # Apply percentile-based thresholds so selection adapts to current score distribution
        try:
            values = np.array([s["strength_score"] for s in scores])
            if len(values) > 0:
                p20 = float(np.percentile(values, 20))
                p80 = float(np.percentile(values, 80))
            else:
                p20 = 0.3
                p80 = 0.7
        except Exception:
            p20 = 0.3
            p80 = 0.7

        for s in scores:
            s["is_weak"] = s["strength_score"] <= p20
            s["is_strong"] = s["strength_score"] >= p80

        scores.sort(key=lambda x: -x["strength_score"])
        return scores

    def _compute_correlation_penalties(self, portfolio: list[dict]) -> list[dict]:
        """Detect correlated clusters and compute penalties."""
        # Group by archetype
        archetype_groups = defaultdict(list)
        for o in portfolio:
            archetype_groups[o.get("archetype", "unknown")].append(o)

        penalties = []
        for archetype, members in archetype_groups.items():
            if len(members) >= 3:  # 3+ same archetype = correlated cluster
                for m in members:
                    penalties.append({
                        "strategy_id": m["id"],
                        "strategy_name": m["name"],
                        "archetype": archetype,
                        "cluster_size": len(members),
                        "correlation_penalty": min(1.0, self.CORRELATION_PENALTY * (len(members) - 2) / 3),
                    })

        return penalties

    def _compute_diversification_rewards(self, portfolio: list[dict], stress_active: bool) -> list[dict]:
        """Compute diversification rewards for unique archetypes."""
        # Count archetype frequency
        archetype_counts = defaultdict(int)
        for o in portfolio:
            archetype_counts[o.get("archetype", "unknown")] += 1

        base_reward_mult = self.STRESS_DIVERSIFICATION_BOOST if stress_active else 1.0

        rewards = []
        for o in portfolio:
            archetype = o.get("archetype", "unknown")
            freq = archetype_counts.get(archetype, 1)
            # Rare archetypes get diversification reward
            if freq == 1:
                reward_mult = self.DIVERSIFICATION_REWARD * base_reward_mult
            elif freq == 2:
                reward_mult = 1.1
            else:
                reward_mult = 1.0

            rewards.append({
                "strategy_id": o["id"],
                "strategy_name": o["name"],
                "archetype": archetype,
                "archetype_frequency": freq,
                "diversification_reward_mult": round(reward_mult, 4),
            })

        return rewards

    def _apply_evolution_pressure(
        self, portfolio: list[dict],
        strength_scores: list[dict],
        dominant_ids: set,
        correlation_penalties: list[dict],
        diversification_rewards: list[dict],
    ) -> list[dict]:
        """Apply evolution pressure to compute adjusted allocations."""
        # Build lookup maps
        strength_map = {s["strategy_id"]: s for s in strength_scores}
        penalty_map = {p["strategy_id"]: p for p in correlation_penalties}
        reward_map = {r["strategy_id"]: r for r in diversification_rewards}

        pressured = []
        for o in portfolio:
            sid = o["id"]
            current_weight = o.get("current_weight", 0)
            strength = strength_map.get(sid, {})
            penalty = penalty_map.get(sid, {})
            reward = reward_map.get(sid, {})

            # Start with current allocation
            adjusted_weight = current_weight

            # Evolution pressure: penalize weak organisms
            if strength.get("is_weak", False):
                reduction = adjusted_weight * 0.3  # 30% reduction
                adjusted_weight -= reduction

            # Evolution pressure: boost dominant organisms
            if sid in dominant_ids:
                boost = adjusted_weight * (self.DOMINANT_BOOST_MULTIPLIER - 1.0)
                adjusted_weight += boost

            # Evolution pressure: correlation penalty
            corr_penalty = penalty.get("correlation_penalty", 0)
            if corr_penalty > 0:
                adjusted_weight *= (1.0 - corr_penalty)

            # Evolution pressure: diversification reward
            div_reward = reward.get("diversification_reward_mult", 1.0)
            adjusted_weight *= div_reward

            evolution_adjustment = adjusted_weight - current_weight

            # Apply min/max constraints
            if strength.get("is_weak", False) and evolution_adjustment < 0:
                adjusted_weight = max(self.MIN_ALLOCATION_WEAK, adjusted_weight)
            if sid in dominant_ids:
                adjusted_weight = min(self.MAX_ALLOCATION_DOMINANT, adjusted_weight)

            # Recompute adjustment after constraints
            evolution_adjustment = adjusted_weight - current_weight

            pressured.append({
                "strategy_id": sid,
                "strategy_name": o.get("name", ""),
                "current_weight": round(current_weight, 4),
                "evolution_adjusted_weight": round(max(0.001, adjusted_weight), 4),
                "evolution_adjustment": round(evolution_adjustment, 4),
                "strength_score": strength.get("strength_score", 0.5),
                "is_weak": strength.get("is_weak", False),
                "is_dominant": sid in dominant_ids,
                "correlation_penalty_applied": corr_penalty > 0,
                "diversification_reward_applied": div_reward > 1.0,
                "archetype": o.get("archetype", "unknown"),
            })

        # Normalize to sum to 1.0
        total_weight = sum(a["evolution_adjusted_weight"] for a in pressured)
        if total_weight > 0:
            for a in pressured:
                a["evolution_adjusted_weight"] = round(a["evolution_adjusted_weight"] / total_weight, 4)
                a["evolution_adjustment"] = round(a["evolution_adjusted_weight"] - a["current_weight"], 4)

        pressured.sort(key=lambda x: -x["evolution_adjusted_weight"])
        return pressured

    def _compute_migration_signals(self, pressured_allocations: list[dict]) -> list[dict]:
        """Compute capital migration signals (where capital should flow)."""
        signals = []
        for a in pressured_allocations:
            if abs(a.get("evolution_adjustment", 0)) > 0.01:  # >1% change
                signals.append({
                    "strategy_id": a["strategy_id"],
                    "strategy_name": a["strategy_name"],
                    "direction": "increase" if a["evolution_adjustment"] > 0 else "decrease",
                    "amount": round(abs(a["evolution_adjustment"]), 4),
                    "archetype": a["archetype"],
                    "reason": self._determine_migration_reason(a),
                })

        signals.sort(key=lambda x: -x["amount"])
        return signals[:20]

    def _determine_migration_reason(self, allocation: dict) -> str:
        """Determine why capital migration is happening."""
        reasons = []
        if allocation.get("is_dominant"):
            reasons.append("dominant_organism_concentration")
        if allocation.get("correlation_penalty_applied"):
            reasons.append("correlation_cluster_penalty")
        if allocation.get("diversification_reward_applied"):
            reasons.append("diversification_reward")
        if allocation.get("is_weak") and allocation.get("evolution_adjustment", 0) < 0:
            reasons.append("weak_organism_starvation")
        if not reasons:
            reasons.append("reequilibration")
        return "; ".join(reasons)

    async def _persist_pressure(self, pressure: dict):
        """Persist evolution pressure."""
        if not self.db:
            return
        try:
            await self.db._execute_insert("""
                INSERT INTO portfolio_evolution_log
                    (id, tracked_at, n_organisms_analyzed,
                     n_dominant_organisms, stress_active,
                     organism_strength_scores, correlation_penalties,
                     diversification_rewards, pressured_allocations,
                     migration_signals, evolution_pressure_stats,
                     metadata)
                VALUES
                    (:id, :tracked_at, :n_organisms_analyzed,
                     :n_dominant_organisms, :stress_active,
                     :organism_strength_scores, :correlation_penalties,
                     :diversification_rewards, :pressured_allocations,
                     :migration_signals, :evolution_pressure_stats,
                     :metadata)
            """, {
                "id": pressure["id"],
                "tracked_at": pressure["computed_at"],
                "n_organisms_analyzed": pressure["n_organisms_analyzed"],
                "n_dominant_organisms": pressure["n_dominant_organisms"],
                "stress_active": pressure["stress_active"],
                "organism_strength_scores": json.dumps(pressure["organism_strength_scores"]),
                "correlation_penalties": json.dumps(pressure["correlation_penalties"]),
                "diversification_rewards": json.dumps(pressure["diversification_rewards"]),
                "pressured_allocations": json.dumps(pressure["pressured_allocations"]),
                "migration_signals": json.dumps(pressure["migration_signals"]),
                "evolution_pressure_stats": json.dumps(pressure["evolution_pressure_stats"]),
                "metadata": json.dumps({"method": "evolutionary_selection_pressure"}),
            })
        except Exception as e:
            logger.warning(f"{self.name}: persist failed: {e}")

    async def get_evolution_pressure_snapshot(self) -> dict:
        """Public method: get current evolution pressure snapshot."""
        return self._latest_pressure
