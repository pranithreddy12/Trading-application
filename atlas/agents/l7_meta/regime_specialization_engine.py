"""regime_specialization_engine.py — Phase 31C: Regime Specialization Engine.

Purpose:
Persistent regime profiling for each organism. Each organism tracks:
  - Bull-market survivability
  - Bear-market survivability
  - Sideways/ranging survivability
  - Volatility tolerance
  - Liquidity sensitivity

Generates regime affinity scores for each organism.

Outputs persisted to organism_regime_profile table and consumed by:
  - PortfolioEvolutionPressure (regime-conditioned capital allocation)
  - DominantOrganismTracker (regime specialists)
  - StrategyRetirementEngine (regime-context retirement decisions)
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


# Regime archetypes
REGIME_TYPES = ["bull_market", "bear_market", "ranging", "high_vol", "low_vol", "trending", "illiquid"]

# Ideal regime profiles for different strategy archetypes
IDEAL_REGIME_MAP = {
    "momentum": {"trending": 1.0, "bull_market": 0.8, "high_vol": 0.6, "ranging": 0.2, "bear_market": 0.1},
    "mean_reversion": {"ranging": 1.0, "low_vol": 0.8, "bear_market": 0.6, "bull_market": 0.4, "trending": 0.2},
    "breakout": {"trending": 0.9, "bull_market": 0.8, "high_vol": 0.7, "ranging": 0.3, "bear_market": 0.1},
    "volatility": {"high_vol": 1.0, "trending": 0.6, "ranging": 0.4, "low_vol": 0.1},
    "scalping": {"low_vol": 0.9, "ranging": 0.7, "high_vol": 0.3, "trending": 0.4},
    "mean_reversion_volatility": {"high_vol": 0.9, "ranging": 0.8, "bear_market": 0.5, "bull_market": 0.3},
    "breakout_momentum": {"trending": 1.0, "bull_market": 0.9, "high_vol": 0.5, "ranging": 0.2},
}


class RegimeSpecializationEngine(BaseAgent):
    """L7 Meta Agent — Persistent regime profiling for organisms."""

    name = "RegimeSpecializationEngine"
    agent_type = "regime_specialization"
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
        self._latest_profiles: dict = {}

    async def run(self):
        logger.info(f"{self.name}: starting regime specialization profiling (every {self.run_interval}s)")
        while self.status == "running":
            try:
                await self._profiling_cycle()
            except Exception as e:
                logger.error(f"{self.name}: profiling cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _profiling_cycle(self):
        """Full profiling cycle."""
        organisms = await self._fetch_organisms()
        if not organisms or len(organisms) < 2:
            logger.info(f"{self.name}: insufficient organisms ({len(organisms) if organisms else 0})")
            return

        # Compute regime profiles for each organism
        profiles = {}
        for o in organisms:
            profile = self._compute_regime_profile(o)
            if profile:
                profiles[o["id"]] = profile

        # Compute aggregate regime affinity scores
        affinity_scores = self._compute_affinity_scores(profiles)

        # Compute ecosystem-level regime specialization
        ecosystem = self._compute_ecosystem_regime_specialization(profiles)

        # Persist
        tracking = {
            "id": str(uuid.uuid4()),
            "profiled_at": datetime.now(timezone.utc),
            "n_organisms_profiled": len(profiles),
            "regime_profiles": profiles,
            "affinity_scores": affinity_scores,
            "ecosystem_regime_specialization": ecosystem,
            "metadata": {"method": "multi_factor_regime_profiling"},
        }

        await self._persist_profiles(tracking)
        self._latest_profiles = profiles

        logger.info(
            f"{self.name}: Profiled {len(profiles)} organisms across "
            f"{len([k for k, v in ecosystem.items() if v > 0.2])} regime dimensions"
        )

    async def _fetch_organisms(self) -> list[dict]:
        """Fetch organisms with backtest results and metadata."""
        if not self.db:
            return []
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        s.id, s.name, s.status, s.lifecycle_state,
                        s.normalized_strategy, s.created_at,
                        b.composite_fitness_score, b.sharpe, b.win_rate,
                        b.total_trades, b.max_drawdown, b.results
                    FROM strategies s
                    LEFT JOIN LATERAL (
                        SELECT composite_fitness_score, sharpe, win_rate,
                               total_trades, max_drawdown, results
                        FROM backtest_results
                        WHERE strategy_id = s.id
                        ORDER BY created_at DESC LIMIT 1
                    ) b ON TRUE
                    WHERE s.status IN ('validated', 'elite', 'promoted', 'live', 'research_candidate')
                    ORDER BY b.composite_fitness_score DESC NULLS LAST
                    LIMIT 100
                """))
                rows = result.fetchall()
                out = []
                for r in rows:
                    ns = r[4]
                    if isinstance(ns, str):
                        try:
                            ns = json.loads(ns)
                        except Exception:
                            ns = {}
                    results_raw = r[11]
                    if isinstance(results_raw, str):
                        try:
                            results_raw = json.loads(results_raw)
                        except Exception:
                            results_raw = {}

                    out.append({
                        "id": str(r[0]),
                        "name": r[1],
                        "status": r[2],
                        "lifecycle_state": r[3] or "active",
                        "archetype": (ns.get("tags") or ["unknown"])[0] if isinstance(ns, dict) else "unknown",
                        "created_at": r[5],
                        "composite_fitness_score": float(r[6] or 0),
                        "sharpe": float(r[7] or 0),
                        "win_rate": float(r[8] or 0),
                        "total_trades": int(r[9] or 0),
                        "max_drawdown": float(r[10] or 0),
                        "profit_factor": float(results_raw.get("profit_factor", 1.0)),
                        "cagr": float(results_raw.get("cagr", 0)),
                        "avg_return_pct": float(results_raw.get("avg_return_pct", results_raw.get("mean_return_pct", 0))),
                        "std_return_pct": float(results_raw.get("std_return_pct", results_raw.get("std_pct", 0.02))),
                        "sortino": float(results_raw.get("sortino_ratio", results_raw.get("sortino", 0))),
                    })
                return out
        except Exception as e:
            logger.warning(f"{self.name}: fetch organisms failed: {e}")
            return []

    def _compute_regime_profile(self, organism: dict) -> dict:
        """Compute regime profile from a single organism's backtest data."""
        sharpe = organism.get("sharpe", 0)
        win_rate = organism.get("win_rate", 0.5)
        max_dd = abs(organism.get("max_drawdown", 0))
        profit_factor = organism.get("profit_factor", 1.0)
        total_trades = organism.get("total_trades", 0)
        score = organism.get("composite_fitness_score", 0)
        cagr = organism.get("cagr", 0)
        sortino = organism.get("sortino", 0)
        std_return = organism.get("std_return_pct", 0.02)
        avg_return = organism.get("avg_return_pct", 0)

        if total_trades < 5:
            return {}

        # Compute regime-specific scores using proxy metrics

        # Bull-market survivability: high sharpe + high CAGR + moderate drawdown
        bull_score = (
            max(0, sharpe) * 0.25
            + max(0, cagr) * 0.25
            + min(1.0, profit_factor / 3.0) * 0.25
            + (1.0 - min(1.0, max_dd / 30)) * 0.25
        )

        # Bear-market survivability: low drawdown + positive sortino + profit factor > 1
        bear_score = (
            (1.0 - min(1.0, max_dd / 40)) * 0.30
            + max(0, sortino) * 0.25
            + min(1.0, max(0, profit_factor) / 2.0) * 0.25
            + max(0, win_rate - 0.4) * 0.20
        )

        # Ranging survivability: high win rate + moderate profit factor + low std
        ranging_score = (
            min(1.0, win_rate * 1.5) * 0.30
            + min(1.0, profit_factor / 2.5) * 0.25
            + (1.0 - min(1.0, std_return * 20)) * 0.25
            + (1.0 - min(1.0, max_dd / 25)) * 0.20
        )

        # Volatility tolerance: high std deviation + positive sharpe + high CAGR
        vol_tolerance = (
            min(1.0, std_return * 50) * 0.25
            + max(0, sharpe) * 0.25
            + min(1.0, cagr * 5) * 0.25
            + min(1.0, avg_return * 100) * 0.25
        )

        # Liquidity sensitivity: uses total_trades as proxy; high trade count = liquid-friendly
        liquidity_sensitivity = min(1.0, (
            1.0 - min(1.0, total_trades / 200) * 0.30  # Illiquid tolerant: low trades OK
            + max(0, win_rate - 0.4) * 0.35
            + min(1.0, profit_factor / 2.0) * 0.35
        ))

        # Archetype-ideal alignment
        archetype = organism.get("archetype", "unknown")
        ideal = IDEAL_REGIME_MAP.get(archetype, {})
        ideal_alignment = ideal.get("trending", 0.5) * bull_score * 0.5 + 0.5

        return {
            "strategy_id": organism["id"],
            "strategy_name": organism["name"],
            "archetype": archetype,
            "bull_survivability": round(float(bull_score), 4),
            "bear_survivability": round(float(bear_score), 4),
            "ranging_survivability": round(float(ranging_score), 4),
            "volatility_tolerance": round(float(vol_tolerance), 4),
            "liquidity_sensitivity": round(float(liquidity_sensitivity), 4),
            "archetype_regime_alignment": round(float(ideal_alignment), 4),
            "primary_affinity": self._determine_primary_affinity(bull_score, bear_score, ranging_score),
            "profile_confidence": round(
                min(1.0, total_trades / 50) * 0.5
                + min(1.0, max(0, sharpe) / 2.0) * 0.3
                + min(1.0, score / 50) * 0.2,
                4,
            ),
        }

    def _determine_primary_affinity(self, bull: float, bear: float, ranging: float) -> str:
        """Determine the regime the organism is most adapted to."""
        scores = {"bull_market": bull, "bear_market": bear, "ranging": ranging}
        return max(scores, key=scores.get)

    def _compute_affinity_scores(self, profiles: dict) -> dict:
        """Compute aggregate affinity scores across the ecosystem."""
        if not profiles:
            return {}

        regime_dims = ["bull_survivability", "bear_survivability", "ranging_survivability",
                       "volatility_tolerance", "liquidity_sensitivity"]

        aggregate = {}
        for dim in regime_dims:
            values = [p.get(dim, 0) for p in profiles.values() if p]
            if values:
                aggregate[dim] = {
                    "mean": round(float(np.mean(values)), 4),
                    "std": round(float(np.std(values)), 4),
                    "max": round(float(np.max(values)), 4),
                    "min": round(float(np.min(values)), 4),
                }

        return aggregate

    def _compute_ecosystem_regime_specialization(self, profiles: dict) -> dict:
        """Compute ecosystem-level regime specialization metrics."""
        if not profiles:
            return {}

        # Count organisms by primary affinity
        affinity_counts = defaultdict(int)
        archetype_counts = defaultdict(lambda: defaultdict(int))
        for p in profiles.values():
            if p:
                affinity_counts[p.get("primary_affinity", "unknown")] += 1
                archetype = p.get("archetype", "unknown")
                archetype_counts[archetype][p.get("primary_affinity", "unknown")] += 1

        total = max(1, len(profiles))
        return {
            "affinity_distribution": {k: {"count": v, "pct": round(v / total, 4)} for k, v in affinity_counts.items()},
            "archetype_regime_mapping": dict(archetype_counts),
            "dominant_affinity": max(affinity_counts, key=affinity_counts.get) if affinity_counts else "unknown",
            "specialization_diversity": round(len(affinity_counts) / max(1, total), 4),
        }

    async def _persist_profiles(self, tracking: dict):
        """Persist regime profiles and affinity scores."""
        if not self.db:
            return
        try:
            # Persist per-organism profiles
            for sid, profile in tracking["regime_profiles"].items():
                if not profile:
                    continue
                await self.db._execute_insert("""
                    INSERT INTO organism_regime_profile
                        (id, strategy_id, profiled_at,
                         bull_survivability, bear_survivability,
                         ranging_survivability, volatility_tolerance,
                         liquidity_sensitivity, archetype_regime_alignment,
                         primary_affinity, profile_confidence,
                         archetype, metadata)
                    VALUES
                        (:id, :strategy_id, :profiled_at,
                         :bull, :bear, :ranging, :vol_tol,
                         :liq_sens, :alignment,
                         :primary_affinity, :confidence,
                         :archetype, :metadata)
                    ON CONFLICT (strategy_id, profiled_at) DO NOTHING
                """, {
                    "id": str(uuid.uuid4())[:16],
                    "strategy_id": sid,
                    "profiled_at": tracking["profiled_at"],
                    "bull": profile["bull_survivability"],
                    "bear": profile["bear_survivability"],
                    "ranging": profile["ranging_survivability"],
                    "vol_tol": profile["volatility_tolerance"],
                    "liq_sens": profile["liquidity_sensitivity"],
                    "alignment": profile["archetype_regime_alignment"],
                    "primary_affinity": profile["primary_affinity"],
                    "confidence": profile["profile_confidence"],
                    "archetype": profile["archetype"],
                    "metadata": json.dumps({"method": "multi_factor_regime_profiling"}),
                })

            # Persist aggregate affinity scores
            await self.db._execute_insert("""
                INSERT INTO regime_specialization_aggregate
                    (id, computed_at, n_organisms_profiled,
                     affinity_scores, ecosystem_specialization, metadata)
                VALUES
                    (:id, :computed_at, :n_organisms,
                     :affinity_scores, :ecosystem, :metadata)
            """, {
                "id": tracking["id"],
                "computed_at": tracking["profiled_at"],
                "n_organisms": tracking["n_organisms_profiled"],
                "affinity_scores": json.dumps(tracking["affinity_scores"]),
                "ecosystem": json.dumps(tracking["ecosystem_regime_specialization"]),
                "metadata": json.dumps(tracking["metadata"]),
            })
        except Exception as e:
            logger.warning(f"{self.name}: persist profiles failed: {e}")

    async def get_organism_regime_profile(self, strategy_id: str) -> Optional[dict]:
        """Public method: get regime profile for a specific organism."""
        return self._latest_profiles.get(strategy_id)

    async def get_ecosystem_regime_summary(self) -> dict:
        """Public method: get ecosystem-level regime specialization summary."""
        return self._compute_ecosystem_regime_specialization(self._latest_profiles)
