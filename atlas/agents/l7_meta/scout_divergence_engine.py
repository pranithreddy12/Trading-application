"""scout_divergence_engine.py — Phase 31D: Scout Predictive Divergence Tracking.

Purpose:
Measures long-horizon economic usefulness of scout signals.
Tracks:
  - Scout contribution to profitable organisms
  - Scout contribution to failed organisms
  - Regime-specific scout usefulness
  - Contradiction penalties
  - Long-term attribution quality

Goal:
Allow epistemic specialization to emerge naturally across the scout network.

Outputs persisted to scout_divergence_log and consumed by:
  - ScoutSynthesisEngine (scout weighting)
  - SourceReliabilityEngine (trust score adjustment)
  - RegimeSpecializationEngine (scout-regime correlation)
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


class ScoutDivergenceEngine(BaseAgent):
    """L7 Meta Agent — Tracks long-horizon scout predictive divergence."""

    name = "ScoutDivergenceEngine"
    agent_type = "scout_divergence"
    layer = "L7"

    def __init__(self, redis_client=None, db_client=None, run_interval: int = 3600):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.run_interval = run_interval

        # Divergence tracking thresholds
        self.ATTRIBUTION_LOOKBACK_HOURS = 168  # 7 days
        self.CONTRADICTION_PENALTY = 0.15       # Score penalty per contradiction detected
        self.MIN_ATTRIBUTIONS_FOR_SCORE = 3     # Minimum attributions to compute score

        self._scout_scores: dict = {}

    async def run(self):
        logger.info(f"{self.name}: starting scout divergence tracking (every {self.run_interval}s)")
        while self.status == "running":
            try:
                await self._divergence_cycle()
            except Exception as e:
                logger.error(f"{self.name}: divergence cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _divergence_cycle(self):
        """Full divergence tracking cycle."""
        # 1. Fetch scout attribution records
        attributions = await self._fetch_scout_attributions()
        if not attributions or len(attributions) < 3:
            logger.info(f"{self.name}: insufficient attributions ({len(attributions) if attributions else 0})")
            return

        # 2. Fetch strategy outcomes (which strategies survived/failed)
        outcomes = await self._fetch_strategy_outcomes()

        # 3. Compute per-scout contribution to profitable organisms
        profit_contribution = self._compute_profit_contribution(attributions, outcomes)

        # 4. Compute per-scout contribution to failed organisms
        failure_contribution = self._compute_failure_contribution(attributions, outcomes)

        # 5. Compute regime-specific scout usefulness
        regime_usefulness = self._compute_regime_usefulness(attributions, outcomes)

        # 6. Compute contradiction penalties
        contradiction_penalties = self._compute_contradiction_penalties(attributions)

        # 7. Compute long-term attribution quality
        attribution_quality = self._compute_attribution_quality(attributions)

        # 8. Compute divergence scores per scout
        divergence_scores = self._compute_divergence_scores(
            profit_contribution, failure_contribution,
            contradiction_penalties, attribution_quality
        )

        tracking = {
            "id": str(uuid.uuid4()),
            "tracked_at": datetime.now(timezone.utc),
            "n_attributions_analyzed": len(attributions),
            "n_scouts_tracked": len(set(a.get("source_scout", "unknown") for a in attributions)),
            "profit_contribution": profit_contribution,
            "failure_contribution": failure_contribution,
            "regime_usefulness": regime_usefulness,
            "contradiction_penalties": contradiction_penalties,
            "attribution_quality": attribution_quality,
            "divergence_scores": divergence_scores,
            "ecosystem_scout_health": {
                "n_active_scouts": len(divergence_scores),
                "n_high_value_scouts": sum(1 for s in divergence_scores if s.get("composite_divergence_score", 0) > 0.6),
                "n_low_value_scouts": sum(1 for s in divergence_scores if s.get("composite_divergence_score", 0) < 0.3),
                "n_contradictory_scouts": sum(1 for s in contradiction_penalties if s.get("contradiction_count", 0) > 2),
            },
        }

        # Persist
        await self._persist_tracking(tracking)
        self._scout_scores = {s["scout_name"]: s for s in divergence_scores}

        logger.info(
            f"{self.name}: Tracked {len(attributions)} attributions across "
            f"{tracking['ecosystem_scout_health']['n_active_scouts']} scouts"
        )

    async def _fetch_scout_attributions(self) -> list[dict]:
        """Fetch scout economic attribution records."""
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        id, source_scout, influence_type, target_agent,
                        strategy_id, strategy_name, attribution_weight,
                        survived_validation,
                        regime_at_time, entropy_at_time,
                        metadata, created_at
                    FROM scout_economic_attribution
                    WHERE created_at > NOW() - INTERVAL ':hours hours'
                    ORDER BY created_at DESC
                    LIMIT 5000
                """.replace(":hours", str(self.ATTRIBUTION_LOOKBACK_HOURS))))
                rows = result.fetchall()
                out = []
                for r in rows:
                    meta = r[10]
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    out.append({
                        "id": str(r[0]),
                        "source_scout": str(r[1]) if r[1] else "unknown",
                        "influence_type": str(r[2]) if r[2] else "unknown",
                        "target_agent": str(r[3]) if r[3] else "unknown",
                        "strategy_id": str(r[4]) if r[4] else "",
                        "strategy_name": str(r[5]) if r[5] else "",
                        "attribution_weight": float(r[6] or 0.5),
                        "confidence": float(r[6] or 0.5),
                        "survived_validation": bool(r[7]) if r[7] is not None else False,
                        "regime_at_time": str(r[8]) if r[8] else "neutral",
                        "entropy_at_time": float(r[9] or 0.5),
                        "before_value": 0.0,
                        "after_value": 0.0,
                        "delta": 0.0,
                        "metadata": meta,
                        "created_at": r[11] if len(r) > 11 else None,
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch attributions failed: {e}")
            return []

    async def _fetch_strategy_outcomes(self) -> dict:
        """Fetch strategy outcomes (survival/failure status)."""
        if not self.db:
            return {}
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT s.id, s.lifecycle_state, s.status,
                           COALESCE(b.composite_fitness_score, 0) AS composite_fitness_score,
                           COALESCE(b.total_trades, 0) AS total_trades,
                           COALESCE(b.sharpe, 0) AS sharpe
                    FROM strategies s
                    LEFT JOIN LATERAL (
                        SELECT composite_fitness_score, total_trades, sharpe
                        FROM backtest_results
                        WHERE strategy_id = s.id
                        ORDER BY created_at DESC LIMIT 1
                    ) b ON TRUE
                    ORDER BY s.created_at DESC
                    LIMIT 500
                """))
                rows = result.fetchall()
                outcomes = {}
                for r in rows:
                    sid = str(r[0])
                    lifecycle = r[1] or "emerging"
                    status = r[2] or "unknown"
                    score = float(r[3] or 0) if r[3] else 0
                    trades = int(r[4] or 0) if r[4] else 0
                    sharpe = float(r[5] or 0) if r[5] else 0

                    # Classify outcome
                    if lifecycle in ("dominant",) or (status in ("validated", "elite", "live", "promoted") and score > 40):
                        outcome = "successful"
                    elif lifecycle in ("retired", "quarantined") or score < 10:
                        outcome = "failed"
                    else:
                        outcome = "neutral"

                    outcomes[sid] = {
                        "outcome": outcome,
                        "lifecycle_state": lifecycle,
                        "status": status,
                        "score": score,
                        "trades": trades,
                        "sharpe": sharpe,
                    }
                return outcomes
        except Exception as e:
            logger.warning(f"{self.name}: fetch outcomes failed: {e}")
            return {}

    def _compute_profit_contribution(self, attributions: list[dict], outcomes: dict) -> list[dict]:
        """Compute per-scout contribution to profitable organisms."""
        scout_success = defaultdict(lambda: {"attributions": 0, "strategies": set(), "total_weight": 0.0})

        for a in attributions:
            scout = a["source_scout"]
            sid = a["strategy_id"]
            outcome = outcomes.get(sid, {}).get("outcome", "neutral")

            if outcome == "successful":
                scout_success[scout]["attributions"] += 1
                scout_success[scout]["strategies"].add(sid)
                scout_success[scout]["total_weight"] += a.get("attribution_weight", 0.5)

        results = []
        for scout, data in scout_success.items():
            results.append({
                "scout_name": scout,
                "n_profitable_attributions": data["attributions"],
                "n_profitable_strategies": len(data["strategies"]),
                "total_attribution_weight": round(data["total_weight"], 4),
                "avg_weight_per_attribution": round(data["total_weight"] / max(1, data["attributions"]), 4),
            })

        results.sort(key=lambda x: -x["n_profitable_attributions"])
        return results

    def _compute_failure_contribution(self, attributions: list[dict], outcomes: dict) -> list[dict]:
        """Compute per-scout contribution to failed organisms."""
        scout_failure = defaultdict(lambda: {"attributions": 0, "strategies": set(), "total_weight": 0.0})

        for a in attributions:
            scout = a["source_scout"]
            sid = a["strategy_id"]
            outcome = outcomes.get(sid, {}).get("outcome", "neutral")

            if outcome == "failed":
                scout_failure[scout]["attributions"] += 1
                scout_failure[scout]["strategies"].add(sid)
                scout_failure[scout]["total_weight"] += a.get("attribution_weight", 0.5)

        results = []
        for scout, data in scout_failure.items():
            results.append({
                "scout_name": scout,
                "n_failed_attributions": data["attributions"],
                "n_failed_strategies": len(data["strategies"]),
                "total_attribution_weight": round(data["total_weight"], 4),
            })

        results.sort(key=lambda x: -x["n_failed_attributions"])
        return results

    def _compute_regime_usefulness(self, attributions: list[dict], outcomes: dict) -> dict:
        """Compute regime-specific scout usefulness."""
        regime_scout = defaultdict(lambda: defaultdict(lambda: {"success": 0, "failure": 0, "neutral": 0}))

        for a in attributions:
            scout = a["source_scout"]
            regime = a.get("regime_at_time", "neutral")
            sid = a["strategy_id"]
            outcome = outcomes.get(sid, {}).get("outcome", "neutral")

            regime_scout[regime][scout][outcome] += 1

        regime_usefulness = {}
        for regime, scout_data in regime_scout.items():
            scout_scores = {}
            for scout, counts in scout_data.items():
                total = counts["success"] + counts["failure"] + counts["neutral"]
                if total >= self.MIN_ATTRIBUTIONS_FOR_SCORE:
                    usefulness = (counts["success"] - counts["failure"]) / total
                    scout_scores[scout] = {
                        "usefulness_score": round(usefulness, 4),
                        "n_attributions": total,
                        "n_success": counts["success"],
                        "n_failure": counts["failure"],
                    }
            if scout_scores:
                regime_usefulness[regime] = scout_scores

        return regime_usefulness

    def _compute_contradiction_penalties(self, attributions: list[dict]) -> list[dict]:
        """Detect scouts that contradict each other on the same strategy."""
        # Group by strategy_id
        strategy_attributions = defaultdict(list)
        for a in attributions:
            if a["strategy_id"]:
                strategy_attributions[a["strategy_id"]].append(a)

        # Detect contradictions: same strategy, different scouts with opposite delta signs
        scout_contradictions = defaultdict(int)
        for sid, attrs in strategy_attributions.items():
            if len(attrs) < 2:
                continue
            # Group by scout, check delta signs
            scout_deltas = defaultdict(list)
            for a in attrs:
                scout_deltas[a["source_scout"]].append(a.get("delta", 0))

            for scout_a, deltas_a in scout_deltas.items():
                for scout_b, deltas_b in scout_deltas.items():
                    if scout_a >= scout_b:
                        continue
                    # Check if they have opposite delta directions
                    avg_delta_a = np.mean(deltas_a) if deltas_a else 0
                    avg_delta_b = np.mean(deltas_b) if deltas_b else 0
                    if (avg_delta_a > 0 and avg_delta_b < 0) or (avg_delta_a < 0 and avg_delta_b > 0):
                        scout_contradictions[scout_a] += 1
                        scout_contradictions[scout_b] += 1

        results = []
        for scout, count in scout_contradictions.items():
            results.append({
                "scout_name": scout,
                "contradiction_count": count,
                "contradiction_penalty": round(min(1.0, count * self.CONTRADICTION_PENALTY), 4),
            })

        results.sort(key=lambda x: -x["contradiction_count"])
        return results

    def _compute_attribution_quality(self, attributions: list[dict]) -> list[dict]:
        """Compute long-term attribution quality per scout."""
        scout_quality = defaultdict(lambda: {
            "total_attributions": 0, "total_confidence": 0.0,
            "total_delta": 0.0, "regime_diversity": set(),
        })

        for a in attributions:
            scout = a["source_scout"]
            scout_quality[scout]["total_attributions"] += 1
            scout_quality[scout]["total_confidence"] += a.get("confidence", 0.5)
            scout_quality[scout]["total_delta"] += a.get("delta", 0)
            scout_quality[scout]["regime_diversity"].add(a.get("regime_at_time", "neutral"))

        results = []
        for scout, data in scout_quality.items():
            n = max(1, data["total_attributions"])
            results.append({
                "scout_name": scout,
                "n_attributions": n,
                "avg_confidence": round(data["total_confidence"] / n, 4),
                "total_delta": round(data["total_delta"], 4),
                "regime_diversity": len(data["regime_diversity"]),
                "attribution_quality_score": round(
                    (data["total_confidence"] / n) * 0.4
                    + min(1.0, abs(data["total_delta"]) / 10) * 0.3
                    + min(1.0, len(data["regime_diversity"]) / 5) * 0.3,
                    4,
                ),
            })

        results.sort(key=lambda x: -x["attribution_quality_score"])
        return results

    def _compute_divergence_scores(
        self, profit_contrib: list[dict], failure_contrib: list[dict],
        contradictions: list[dict], quality: list[dict],
    ) -> list[dict]:
        """Compute composite divergence scores per scout."""
        # Build lookup maps
        profit_map = {p["scout_name"]: p for p in profit_contrib}
        failure_map = {f["scout_name"]: f for f in failure_contrib}
        contradiction_map = {c["scout_name"]: c for c in contradictions}
        quality_map = {q["scout_name"]: q for q in quality}

        all_scouts = set(profit_map.keys()) | set(failure_map.keys()) | set(quality_map.keys())

        scores = []
        for scout in all_scouts:
            p = profit_map.get(scout, {})
            f = failure_map.get(scout, {})
            c = contradiction_map.get(scout, {})
            q = quality_map.get(scout, {})

            n_profitable = p.get("n_profitable_attributions", 0)
            n_failed = f.get("n_failed_attributions", 0)
            total = n_profitable + n_failed
            contradiction_penalty = c.get("contradiction_penalty", 0)
            quality_score = q.get("attribution_quality_score", 0.5)

            # Predictive divergence: net positive contribution
            if total >= self.MIN_ATTRIBUTIONS_FOR_SCORE:
                net_contribution = (n_profitable - n_failed) / total
            else:
                net_contribution = 0.0

            # Composite divergence score
            composite = (
                max(0, net_contribution) * 0.35
                + quality_score * 0.30
                + (1.0 - contradiction_penalty) * 0.20
                + min(1.0, total / 20) * 0.15
            )

            scores.append({
                "scout_name": scout,
                "composite_divergence_score": round(composite, 4),
                "net_contribution": round(net_contribution, 4),
                "n_profitable": n_profitable,
                "n_failed": n_failed,
                "total_attributions": total,
                "attribution_quality": quality_score,
                "contradiction_penalty": contradiction_penalty,
            })

        scores.sort(key=lambda x: -x["composite_divergence_score"])
        return scores

    async def _persist_tracking(self, tracking: dict):
        """Persist scout divergence tracking."""
        if not self.db:
            return
        try:
            await self.db._execute_insert("""
                INSERT INTO scout_divergence_log
                    (id, tracked_at, n_attributions_analyzed,
                     n_scouts_tracked, profit_contribution,
                     failure_contribution, regime_usefulness,
                     contradiction_penalties, attribution_quality,
                     divergence_scores, ecosystem_scout_health,
                     metadata)
                VALUES
                    (:id, :tracked_at, :n_attributions_analyzed,
                     :n_scouts_tracked, :profit_contribution,
                     :failure_contribution, :regime_usefulness,
                     :contradiction_penalties, :attribution_quality,
                     :divergence_scores, :ecosystem_scout_health,
                     :metadata)
            """, {
                "id": tracking["id"],
                "tracked_at": tracking["tracked_at"],
                "n_attributions_analyzed": tracking["n_attributions_analyzed"],
                "n_scouts_tracked": tracking["n_scouts_tracked"],
                "profit_contribution": json.dumps(tracking["profit_contribution"]),
                "failure_contribution": json.dumps(tracking["failure_contribution"]),
                "regime_usefulness": json.dumps(tracking["regime_usefulness"]),
                "contradiction_penalties": json.dumps(tracking["contradiction_penalties"]),
                "attribution_quality": json.dumps(tracking["attribution_quality"]),
                "divergence_scores": json.dumps(tracking["divergence_scores"]),
                "ecosystem_scout_health": json.dumps(tracking["ecosystem_scout_health"]),
                "metadata": json.dumps({"method": "multi_factor_divergence_scoring"}),
            })
        except Exception as e:
            logger.warning(f"{self.name}: persist failed: {e}")

    async def get_scout_divergence(self, scout_name: str) -> Optional[dict]:
        """Public method: get divergence score for a specific scout."""
        return self._scout_scores.get(scout_name)

    async def get_all_scout_scores(self) -> list[dict]:
        """Public method: get all scout divergence scores."""
        return list(self._scout_scores.values())
