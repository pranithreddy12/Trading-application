"""
feature_importance_engine.py — Phase 11: Feature Importance & Attribution.

Tracks and analyzes:
  - Predictive feature ranking (which features drive strategy performance)
  - Feature decay (how feature importance changes over time)
  - Regime-conditioned importance (features that matter in specific regimes)
  - Mutation attribution (which feature changes improved performance)
  - Feature survival analysis (which features persist in top strategies)

Outputs:
  - feature_importance_tables: per-archetype feature rankings
  - feature_decay_curves: importance over time
  - adaptive_feature_rankings: regime-conditioned feature scores

Feeds into:
  - Ideator: prefer important features, deprecate decaying ones
  - Mutator: target important features for mutation
  - Validator: prioritize feature-robust strategies
"""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

import numpy as np
from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class FeatureImportanceEngine(BaseAgent):
    """
    Feature Importance Engine — tracks predictive feature value and decay.

    Configuration:
      - run_interval: seconds between analysis cycles (default 7200 = 2 hours)
      - decay_half_life: half-life in days for importance decay (default 30)
    """

    name = "FeatureImportanceEngine"
    agent_type = "feature_importance"
    layer = "L7"

    # Features tracked for importance analysis
    FEATURE_NAMES = [
        "rsi_14", "macd", "macd_signal", "vwap",
        "price_vs_vwap_pct", "ema_spread_pct", "bollinger_band_position",
        "relative_volume", "rolling_volatility", "trend_strength",
        "sma_5", "sma_20", "ema_5", "ema_12", "ema_26",
    ]

    def __init__(
        self,
        redis_client=None,
        db_client=None,
        run_interval: int = 7200,
    ):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.run_interval = run_interval

    async def run(self):
        logger.info(f"{self.name}: starting feature importance analysis (every {self.run_interval}s)")
        while self.status == "running":
            try:
                rankings = await self._compute_feature_rankings()
                if rankings:
                    await self._persist_rankings(rankings)
                    await self._publish(rankings)
            except Exception as e:
                logger.error(f"{self.name}: analysis failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _compute_feature_rankings(self) -> list[dict]:
        """
        Compute feature importance rankings by analyzing:
        1. Strategy performance vs feature usage
        2. Feature survival in top strategies
        3. Feature decay over time
        """
        if not self.db:
            return []

        # Fetch strategies with backtest results and normalized_strategy
        strategies = await self._fetch_recent_strategies()
        if not strategies:
            return []

        # Count feature usage in successful vs failed strategies
        feature_scores: dict[str, list[float]] = defaultdict(list)
        feature_archetype: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        feature_times: dict[str, list[datetime]] = defaultdict(list)

        for s in strategies:
            params = s.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}

            # Extract features from normalized strategy
            ns = params.get("normalized_strategy", params)
            if isinstance(ns, str):
                try:
                    ns = json.loads(ns)
                except Exception:
                    ns = {}

            features_used = self._extract_features(ns)
            if not features_used:
                continue

            score = s.get("composite_score", s.get("short_window_score", 0)) or 0
            score = float(score)
            archetype = s.get("archetype", "unknown")
            created_at = s.get("created_at", datetime.utcnow())

            for feat in features_used:
                if feat in self.FEATURE_NAMES:
                    feature_scores[feat].append(score)
                    feature_archetype[feat][archetype] += 1
                    feature_times[feat].append(created_at)

        if not feature_scores:
            return []

        rankings = []
        for feat, scores in feature_scores.items():
            if len(scores) < 3:
                continue

            avg_score = float(np.mean(scores))
            std_score = float(np.std(scores)) + 1e-10
            n_uses = len(scores)

            # Importance score: higher avg score + more consistent
            importance = avg_score / (std_score + 0.1)
            importance = min(1.0, max(0.0, importance / 100.0))

            # Survival rate: fraction of scores above 50
            survival_rate = float(np.mean(np.array(scores) >= 50))

            # Dominant archetype
            dominant_arch = max(feature_archetype[feat], key=feature_archetype[feat].get)
            arch_focus = feature_archetype[feat][dominant_arch] / n_uses if n_uses > 0 else 0

            # Decay: importance of recent vs older uses
            decay_score = 1.0
            if len(feature_times[feat]) >= 10:
                times = sorted(feature_times[feat])
                mid = len(times) // 2
                recent_scores = [s for t, s in zip(sorted(feature_times[feat], key=lambda x: x, reverse=True), scores[:mid])]
                older_scores = [s for t, s in zip(sorted(feature_times[feat]), scores[-mid:])]
                if recent_scores and older_scores:
                    recent_avg = float(np.mean(recent_scores))
                    older_avg = float(np.mean(older_scores))
                    if older_avg > 0:
                        decay_score = min(1.0, recent_avg / older_avg)

            rankings.append({
                "feature_name": feat,
                "feature_importance_score": round(importance, 4),
                "avg_composite_score": round(avg_score, 2),
                "std_composite_score": round(std_score, 2),
                "n_uses": n_uses,
                "survival_rate": round(survival_rate, 4),
                "decay_score": round(decay_score, 4),
                "dominant_archetype": dominant_arch,
                "archetype_focus_pct": round(arch_focus * 100, 1),
                "top_archetypes": dict(sorted(feature_archetype[feat].items(), key=lambda x: -x[1])[:3]),
            })

        # Sort by importance
        rankings.sort(key=lambda r: -r["feature_importance_score"])
        return rankings

    def _extract_features(self, ns: dict) -> list[str]:
        """Extract feature names from a normalized strategy spec."""
        features = []
        for key in ("entry_conditions", "exit_conditions"):
            conds = ns.get(key, [])
            if isinstance(conds, list):
                import re
                for cond in conds:
                    if isinstance(cond, str):
                        found = re.findall(r"\b[a-z_][a-z_0-9]+\b", cond)
                        for feat in found:
                            if feat in self.FEATURE_NAMES:
                                features.append(feat)
        return features

    async def _fetch_recent_strategies(self) -> list[dict]:
        """Fetch recent strategies with backtest results."""
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(
                    text("""
                        SELECT s.id, s.name, s.parameters, s.normalized_strategy,
                               s.status, s.created_at,
                               b.short_window_score, b.results
                        FROM strategies s
                        JOIN backtest_results b ON s.id = b.strategy_id
                        WHERE b.short_window_score IS NOT NULL
                        ORDER BY s.created_at DESC
                        LIMIT 200
                    """)
                )
                rows = result.fetchall()
                out = []
                for r in rows:
                    params = r[2]
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except Exception:
                            params = {}
                    ns = r[3]
                    if isinstance(ns, str):
                        try:
                            ns = json.loads(ns)
                        except Exception:
                            ns = {}

                    results_raw = r[7] if r[7] else {}
                    if isinstance(results_raw, str):
                        try:
                            results_raw = json.loads(results_raw)
                        except Exception:
                            results_raw = {}

                    archetype = "unknown"
                    if isinstance(ns, dict) and "tags" in ns:
                        tags = ns["tags"]
                        if tags and isinstance(tags, list):
                            archetype = tags[0]
                    elif isinstance(params, dict) and "tags" in params:
                        tags = params["tags"]
                        if tags and isinstance(tags, list):
                            archetype = tags[0]

                    out.append({
                        "id": str(r[0]),
                        "parameters": params,
                        "normalized_strategy": ns,
                        "status": r[4],
                        "created_at": r[5],
                        "short_window_score": float(r[6]) if r[6] is not None else 0,
                        "composite_score": float(results_raw.get("composite_score", results_raw.get("composite_score_avg", 0))),
                        "archetype": archetype,
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch strategies failed: {e}")
            return []

    async def _persist_rankings(self, rankings: list[dict]) -> None:
        """Persist feature rankings to feature_importance table."""
        if not self.db:
            return
        now = datetime.utcnow()
        for r in rankings:
            try:
                await self.db._execute_insert(
                    """
                    INSERT INTO feature_importance
                        (id, feature_name, feature_importance_score, avg_composite_score,
                         std_composite_score, n_uses, survival_rate, decay_score,
                         dominant_archetype, archetype_focus_pct, top_archetypes,
                         computed_at)
                    VALUES
                        (:id, :fn, :fis, :acs, :scs, :nu, :sr, :ds,
                         :da, :afp, :ta, :ca)
                    ON CONFLICT (feature_name) DO UPDATE SET
                        feature_importance_score = EXCLUDED.feature_importance_score,
                        avg_composite_score = EXCLUDED.avg_composite_score,
                        n_uses = EXCLUDED.n_uses,
                        survival_rate = EXCLUDED.survival_rate,
                        decay_score = EXCLUDED.decay_score,
                        computed_at = EXCLUDED.computed_at
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "fn": r["feature_name"],
                        "fis": r["feature_importance_score"],
                        "acs": r["avg_composite_score"],
                        "scs": r["std_composite_score"],
                        "nu": r["n_uses"],
                        "sr": r["survival_rate"],
                        "ds": r["decay_score"],
                        "da": r["dominant_archetype"],
                        "afp": r["archetype_focus_pct"],
                        "ta": json.dumps(r["top_archetypes"]),
                        "ca": now,
                    },
                )
            except Exception as e:
                logger.warning(f"{self.name}: persist ranking failed: {e}")

    async def _publish(self, rankings: list[dict]) -> None:
        """Publish feature importance rankings to Redis."""
        if not self._redis:
            return
        try:
            signal = {
                "type": "feature_importance",
                "computed_at": datetime.utcnow().isoformat(),
                "total_features": len(rankings),
                "top_features": [{"name": r["feature_name"], "importance": r["feature_importance_score"]} for r in rankings[:10]],
                "top_decaying": [{"name": r["feature_name"], "decay": r["decay_score"]} for r in sorted(rankings, key=lambda x: x["decay_score"])[:5]],
            }
            await self._redis.publish("feature_importance_updates", json.dumps(signal))
        except Exception as e:
            logger.warning(f"{self.name}: publish failed: {e}")

    async def get_feature_importance_snapshot(self) -> dict:
        """
        Public method for Ideator/Mutator to get current feature rankings.
        Returns: { feature_name: importance_score, ... }
        """
        return {r["feature_name"]: r["feature_importance_score"] for r in await self._compute_feature_rankings()}
