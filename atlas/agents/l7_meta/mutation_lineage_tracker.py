"""mutation_lineage_tracker.py — Phase 31B: Mutation Lineage Tracking.

Purpose:
Tracks evolutionary lineage of mutation families over time:
  - Assigns lineage IDs to mutation families
  - Tracks parent→child mutation trees
  - Tracks mutation-family survival rates
  - Tracks mutation-family regime specialization
  - Tracks mutation-family drawdown behavior

Goal:
Determine whether superior mutation families emerge naturally over time.

Outputs persisted to mutation_lineage_log and consumed by:
  - DominantOrganismTracker (mutation family resilience)
  - MutationPolicyEngine (which lineages to prioritize)
  - PortfolioEvolutionPressure (which lineages to fund)
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


class MutationLineageTracker(BaseAgent):
    """L7 Meta Agent — Tracks evolutionary mutation lineages."""

    name = "MutationLineageTracker"
    agent_type = "mutation_lineage_tracker"
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

        # Lineage tracking thresholds
        self.MIN_GENERATIONS_FOR_FAMILY = 2   # Minimum parent→child generations
        self.MIN_MEMBERS_FOR_FAMILY = 3        # Minimum members to form a family
        self.LINEAGE_RECENCY_DAYS = 14         # How far back to track

        self._lineage_cache: dict = {}

    async def run(self):
        logger.info(f"{self.name}: starting mutation lineage tracking (every {self.run_interval}s)")
        while self.status == "running":
            try:
                await self._lineage_cycle()
            except Exception as e:
                logger.error(f"{self.name}: lineage cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _lineage_cycle(self):
        """Full lineage cycle: build trees, compute survival, persist."""
        # 1. Fetch mutation records
        mutations = await self._fetch_mutation_records()
        if not mutations or len(mutations) < 3:
            logger.info(f"{self.name}: insufficient mutations for lineage tracking ({len(mutations) if mutations else 0})")
            return

        # 2. Build parent→child trees
        trees = self._build_mutation_trees(mutations)

        # 3. Assign lineage IDs
        lineages = self._assign_lineage_ids(trees)

        # 4. Compute lineage survival rates
        survival_rates = self._compute_lineage_survival(lineages, mutations)

        # 5. Compute regime specialization per lineage
        regime_specialization = await self._compute_lineage_regime_specialization(lineages)

        # 6. Compute drawdown behavior per lineage
        drawdown_behavior = await self._compute_lineage_drawdown_behavior(lineages)

        # 7. Determine emerging dominant lineages
        dominant_lineages = self._identify_dominant_lineages(
            lineages, survival_rates, regime_specialization
        )

        tracking = {
            "id": str(uuid.uuid4()),
            "tracked_at": datetime.now(timezone.utc),
            "n_mutations_analyzed": len(mutations),
            "n_lineages_identified": len(lineages),
            "n_dominant_lineages": len(dominant_lineages),
            "lineages": lineages,
            "survival_rates": survival_rates,
            "regime_specialization": regime_specialization,
            "drawdown_behavior": drawdown_behavior,
            "dominant_lineages": dominant_lineages,
            "ecosystem_stats": {
                "n_trees": len(trees),
                "avg_depth": round(float(np.mean([t.get("depth", 0) for t in trees])), 2) if trees else 0,
                "max_depth": max([t.get("depth", 0) for t in trees]) if trees else 0,
                "n_singletons": sum(1 for t in trees if len(t.get("members", [])) < 2),
            },
        }

        # Persist
        await self._persist_tracking(tracking)
        self._lineage_cache = {l["lineage_id"]: l for l in lineages}

        logger.info(
            f"{self.name}: Tracked {len(mutations)} mutations → "
            f"{len(lineages)} lineages, {len(dominant_lineages)} dominant"
        )

    async def _fetch_mutation_records(self) -> list[dict]:
        """Fetch mutation memory records with backtest outcomes."""
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        m.id, m.parent_strategy_id, m.child_strategy_id, m.mutation_type,
                        m.parent_sharpe, m.child_sharpe, m.created_at,
                        COALESCE(br.composite_fitness_score, 0) AS child_score,
                        COALESCE(br.sharpe, 0) AS child_sharpe,
                        COALESCE(br.win_rate, 0) AS child_win_rate,
                        COALESCE(br.max_drawdown, 0) AS child_drawdown
                    FROM mutation_memory m
                    LEFT JOIN LATERAL (
                        SELECT composite_fitness_score, sharpe, win_rate, max_drawdown
                        FROM backtest_results
                        WHERE strategy_id = m.child_strategy_id
                        ORDER BY created_at DESC LIMIT 1
                    ) br ON TRUE
                    WHERE m.created_at > NOW() - INTERVAL ':days days'
                    ORDER BY m.created_at DESC
                    LIMIT 1000
                """.replace(":days", str(self.LINEAGE_RECENCY_DAYS))))
                rows = result.fetchall()
                out = []
                for r in rows:
                    out.append({
                        "id": str(r[0]),
                        "parent_id": str(r[1]) if r[1] else "",
                        "child_id": str(r[2]) if r[2] else "",
                        "mutation_type": str(r[3]) if r[3] else "unknown",
                        "parent_sharpe": float(r[4] or 0) if r[4] is not None else 0.0,
                        "child_sharpe_raw": float(r[5] or 0) if r[5] is not None else 0.0,
                        "created_at": r[6],
                        "child_score": float(r[7] or 0),
                        "child_sharpe": float(r[8] or 0),
                        "child_win_rate": float(r[9] or 0),
                        "child_drawdown": float(r[10] or 0),
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch mutations failed: {e}")
            return []

    def _build_mutation_trees(self, mutations: list[dict]) -> list[dict]:
        """Build parent→child trees from mutation records."""
        # Build adjacency: parent_id -> list of child mutations
        children_of = defaultdict(list)
        for m in mutations:
            if m["parent_id"]:
                children_of[m["parent_id"]].append(m)

        # Also build parent lookup
        parent_of = {}
        for m in mutations:
            if m["parent_id"] and m["child_id"]:
                parent_of[m["child_id"]] = m["parent_id"]

        # Find roots (strategies that are parents but not children)
        all_child_ids = {m["child_id"] for m in mutations if m["child_id"]}
        all_parent_ids = {m["parent_id"] for m in mutations if m["parent_id"]}
        root_ids = all_parent_ids - all_child_ids

        # If no clear roots, use the earliest mutations as roots
        if not root_ids and mutations:
            # Group by parent_id and pick earliest per group
            earliest_per_parent = {}
            for m in mutations:
                pid = m["parent_id"]
                if pid and (pid not in earliest_per_parent or m["created_at"] < earliest_per_parent[pid]["created_at"]):
                    earliest_per_parent[pid] = m
            root_ids = set(earliest_per_parent.keys()) - all_child_ids
            if not root_ids and earliest_per_parent:
                # Just use all unique parent_ids as roots
                root_ids = set(earliest_per_parent.keys())

        # Build trees via BFS/DFS
        trees = []
        visited = set()

        for root_id in root_ids:
            if root_id in visited or not root_id:
                continue

            tree = self._build_single_tree(root_id, children_of, parent_of, visited)
            if tree and len(tree.get("members", [])) >= 1:
                trees.append(tree)

        return trees

    def _build_single_tree(
        self, root_id: str,
        children_of: dict,
        parent_of: dict,
        visited: set,
        depth: int = 0,
        max_depth: int = 20,
    ) -> Optional[dict]:
        """Build a single mutation tree from root."""
        if root_id in visited or depth > max_depth:
            return None

        visited.add(root_id)
        members = [{"strategy_id": root_id, "depth": depth, "role": "root"}]

        # BFS for children
        queue = [(root_id, depth)]
        while queue:
            current_id, current_depth = queue.pop(0)
            for child_mutation in children_of.get(current_id, []):
                child_id = child_mutation["child_id"]
                if child_id and child_id not in visited:
                    visited.add(child_id)
                    members.append({
                        "strategy_id": child_id,
                        "depth": current_depth + 1,
                        "role": "child",
                        "mutation_type": child_mutation["mutation_type"],
                        "child_score": child_mutation["child_score"],
                        "child_sharpe": child_mutation["child_sharpe"],
                        "child_win_rate": child_mutation["child_win_rate"],
                        "child_drawdown": child_mutation["child_drawdown"],
                    })
                    if current_depth + 1 < max_depth:
                        queue.append((child_id, current_depth + 1))

        return {
            "root_id": root_id,
            "depth": max(m["depth"] for m in members),
            "n_members": len(members),
            "members": members,
        }

    def _assign_lineage_ids(self, trees: list[dict]) -> list[dict]:
        """Assign lineage IDs to trees and their members."""
        lineages = []
        for tree in trees:
            if tree["n_members"] < self.MIN_MEMBERS_FOR_FAMILY:
                continue

            lineage_id = str(uuid.uuid4())[:12]
            # Extract mutation types in this lineage
            mutation_types = set()
            for m in tree["members"]:
                if m.get("mutation_type"):
                    mutation_types.add(m["mutation_type"])

            # Compute aggregate stats
            scores = [m.get("child_score", 0) for m in tree["members"] if m.get("role") == "child"]
            avg_score = float(np.mean(scores)) if scores else 0
            max_score = float(np.max(scores)) if scores else 0
            sharpe_values = [m.get("child_sharpe", 0) for m in tree["members"] if m.get("role") == "child"]
            avg_sharpe = float(np.mean(sharpe_values)) if sharpe_values else 0

            lineages.append({
                "lineage_id": lineage_id,
                "root_id": tree["root_id"],
                "depth": tree["depth"],
                "n_members": tree["n_members"],
                "n_generations": tree["depth"] + 1,
                "mutation_types": list(mutation_types),
                "members": tree["members"],
                "avg_child_score": round(avg_score, 2),
                "max_child_score": round(max_score, 2),
                "avg_child_sharpe": round(avg_sharpe, 2),
            })

        # Sort by size (largest lineages first)
        lineages.sort(key=lambda x: -x["n_members"])
        return lineages

    def _compute_lineage_survival(self, lineages: list[dict], mutations: list[dict]) -> list[dict]:
        """Compute survival rates per lineage."""
        # Build child_id -> score map
        child_scores = {}
        for m in mutations:
            if m["child_id"]:
                child_scores[m["child_id"]] = m["child_score"]

        survival_results = []
        for lineage in lineages:
            members = lineage["members"]
            n_total = len(members)
            n_survived = sum(
                1 for m in members
                if m.get("role") == "child" and child_scores.get(m["strategy_id"], 0) > 30
            )
            # Include root as survived if it has any children
            root_survived = any(
                child_scores.get(m["strategy_id"], 0) > 20
                for m in members if m.get("role") == "child"
            )
            if root_survived:
                n_survived += 1

            survival_results.append({
                "lineage_id": lineage["lineage_id"],
                "root_id": lineage["root_id"],
                "n_total": n_total,
                "n_survived": n_survived,
                "survival_rate": round(n_survived / max(1, n_total), 4),
                "n_generations": lineage["n_generations"],
            })

        survival_results.sort(key=lambda x: -x["survival_rate"])
        return survival_results

    async def _compute_lineage_regime_specialization(self, lineages: list[dict]) -> dict:
        """Compute regime specialization per lineage (proxy)."""
        if not self.db or not lineages:
            return {}

        # Compute aggregate regime affinity by lineage
        # Uses strategy lifecycle_state as proxy for regime specialization
        lineage_specialization = {}
        for lineage in lineages:
            member_ids = [m["strategy_id"] for m in lineage["members"]]
            if not member_ids:
                continue

            try:
                async with self.db.engine.connect() as conn:
                    placeholders = ", ".join(f"'{sid}'" for sid in member_ids[:50])
                    result = await conn.execute(text(f"""
                        SELECT
                            s.lifecycle_state,
                            COUNT(*) AS cnt,
                            COALESCE(AVG(br.composite_fitness_score), 0) AS avg_score
                        FROM strategies s
                        LEFT JOIN LATERAL (
                            SELECT composite_fitness_score FROM backtest_results
                            WHERE strategy_id = s.id
                            ORDER BY created_at DESC LIMIT 1
                        ) br ON TRUE
                        WHERE s.id IN ({placeholders})
                        GROUP BY s.lifecycle_state
                    """))
                    rows = result.fetchall()
                    state_dist = {str(r[0]): {"count": int(r[1]), "avg_score": float(r[2] or 0)} for r in rows} if rows else {}
            except Exception:
                state_dist = {}

            lineage_specialization[lineage["lineage_id"]] = {
                "lifecycle_distribution": state_dist,
                "n_specialized_states": len(state_dist),
                "dominant_state": max(state_dist, key=lambda k: state_dist[k]["count"]) if state_dist else "unknown",
            }

        return lineage_specialization

    async def _compute_lineage_drawdown_behavior(self, lineages: list[dict]) -> dict:
        """Compute drawdown behavior per lineage."""
        lineage_dd = {}
        for lineage in lineages:
            member_ids = [m["strategy_id"] for m in lineage["members"]]
            dd_values = [m.get("child_drawdown", 0) for m in lineage["members"] if m.get("role") == "child"]
            if dd_values:
                lineage_dd[lineage["lineage_id"]] = {
                    "avg_drawdown": round(float(np.mean(dd_values)), 2),
                    "max_drawdown": round(float(np.max(dd_values)), 2),
                    "min_drawdown": round(float(np.min(dd_values)), 2),
                    "n_members_with_dd": len(dd_values),
                }
            else:
                lineage_dd[lineage["lineage_id"]] = {
                    "avg_drawdown": 0.0,
                    "max_drawdown": 0.0,
                    "min_drawdown": 0.0,
                    "n_members_with_dd": 0,
                }
        return lineage_dd

    def _identify_dominant_lineages(
        self, lineages: list[dict],
        survival_rates: list[dict],
        regime_specialization: dict,
    ) -> list[dict]:
        """Identify which lineages show dominant emergence patterns."""
        survival_map = {s["lineage_id"]: s for s in survival_rates}
        dominant = []

        for lineage in lineages:
            lid = lineage["lineage_id"]
            survival = survival_map.get(lid, {})
            spec = regime_specialization.get(lid, {})

            # Composite dominance score
            score = 0
            factors = []

            # Size factor
            if lineage["n_members"] >= 5:
                score += 20
                factors.append("large_family")
            elif lineage["n_members"] >= 3:
                score += 10
                factors.append("medium_family")

            # Depth factor (more generations = more evolved)
            if lineage["n_generations"] >= 4:
                score += 25
                factors.append("deep_lineage")
            elif lineage["n_generations"] >= 2:
                score += 15
                factors.append("evolving_lineage")

            # Survival factor
            surv_rate = survival.get("survival_rate", 0)
            if surv_rate > 0.5:
                score += 20
                factors.append("high_survival")
            elif surv_rate > 0.3:
                score += 10
                factors.append("moderate_survival")

            # Quality factor
            if lineage["avg_child_score"] > 40:
                score += 15
                factors.append("high_quality")
            elif lineage["avg_child_score"] > 25:
                score += 8
                factors.append("moderate_quality")

            # Specialization factor
            n_states = spec.get("n_specialized_states", 0)
            if n_states >= 2:
                score += 10
                factors.append("regime_specialized")
            elif n_states >= 1:
                score += 5

            dominant.append({
                "lineage_id": lid,
                "root_id": lineage["root_id"],
                "n_members": lineage["n_members"],
                "n_generations": lineage["n_generations"],
                "mutation_types": lineage["mutation_types"],
                "dominance_score": score,
                "dominance_factors": factors,
                "survival_rate": surv_rate,
                "avg_child_score": lineage["avg_child_score"],
                "avg_child_sharpe": lineage["avg_child_sharpe"],
            })

        dominant.sort(key=lambda x: -x["dominance_score"])
        return dominant[:10]

    async def _persist_tracking(self, tracking: dict):
        """Persist lineage tracking to mutation_lineage_log table."""
        if not self.db:
            return
        try:
            await self.db._execute_insert("""
                INSERT INTO mutation_lineage_log
                    (id, tracked_at, n_mutations_analyzed,
                     n_lineages_identified, n_dominant_lineages,
                     lineages, survival_rates, regime_specialization,
                     drawdown_behavior, dominant_lineages,
                     ecosystem_stats, metadata)
                VALUES
                    (:id, :tracked_at, :n_mutations_analyzed,
                     :n_lineages_identified, :n_dominant_lineages,
                     :lineages, :survival_rates, :regime_specialization,
                     :drawdown_behavior, :dominant_lineages,
                     :ecosystem_stats, :metadata)
            """, {
                "id": tracking["id"],
                "tracked_at": tracking["tracked_at"],
                "n_mutations_analyzed": tracking["n_mutations_analyzed"],
                "n_lineages_identified": tracking["n_lineages_identified"],
                "n_dominant_lineages": tracking["n_dominant_lineages"],
                "lineages": json.dumps(tracking["lineages"]),
                "survival_rates": json.dumps(tracking["survival_rates"]),
                "regime_specialization": json.dumps(tracking["regime_specialization"]),
                "drawdown_behavior": json.dumps(tracking["drawdown_behavior"]),
                "dominant_lineages": json.dumps(tracking["dominant_lineages"]),
                "ecosystem_stats": json.dumps(tracking["ecosystem_stats"]),
                "metadata": json.dumps({"method": "bfs_tree_building"}),
            })
        except Exception as e:
            logger.warning(f"{self.name}: persist failed: {e}")

    async def get_lineage_summary(self) -> dict:
        """Public method: return current lineage tracking summary."""
        return dict(self._lineage_cache)

    async def get_lineage_dominance(self, lineage_id: str) -> Optional[dict]:
        """Public method: check dominance status of a specific lineage."""
        return self._lineage_cache.get(lineage_id)
