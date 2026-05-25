"""
regime_stress_engine.py — Phase 30C/31F: Regime Stress Engineering.

Phase 30C:
  Exposes strategies to synthetic market perturbations that they wouldn't
  naturally encounter during benign conditions. Forces regime specialization
  and adaptive selection pressure by injecting controlled environment shocks.

Phase 31F — Enhanced Economic Survival Stress:
  Adds synthetic volatility spikes, liquidity droughts, spread explosions,
  execution degradation, trend reversals, and correlation breaks.
  Observes which organisms collapse, which survive, which adapt, and which
  mutation families dominate under stress.

Perturbation types:
  - Volatility spikes (2x-5x baseline vol)
  - Liquidity compression / droughts (spread widening, volume drop)
  - Trend reversals (sudden 180° price movements)
  - Execution latency spikes
  - Regime flips (bull→bear, ranging→high_vol)
  - Correlation breaks (cross-asset correlation structure disruption)
  - Liquidity drought (extended period of severely reduced volume)
  - Spread explosion (bid-ask spread widens 10x-25x)
  - Execution degradation (fill rates drop, slippage increases)

Each perturbation is synthetic metadata — NOT actual market data manipulation.
The engine writes perturbation signals to DB tables that downstream agents
(scouts, validators, ideators) consume to test strategy robustness.

OUTPUTS:
  - regime_perturbation_events table entries
  - regime_stress_resilience table (per-strategy resilience scoring)
  - Redis channel "regime_stress:current" with active perturbations
"""

import asyncio
import json
import math
import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


# ─────────────────────────────────────────────────────────
# PERTURBATION PRESETS — Phase 30C + Phase 31F extended
# ─────────────────────────────────────────────────────────

PERTURBATION_PRESETS = {
    # Phase 30C — Original perturbations
    "volatility_spike": {
        "description": "Sudden 2x-5x volatility spike lasting 15-60 minutes",
        "type": "volatility",
        "severity_range": (2.0, 5.0),
        "duration_minutes_range": (15, 60),
        "affected_channels": ["regime_detection", "position_sizing"],
    },
    "liquidity_compression": {
        "description": "Spread widens 3x-10x, volume drops 50-90%",
        "type": "liquidity",
        "severity_range": (3.0, 10.0),
        "duration_minutes_range": (10, 45),
        "affected_channels": ["execution", "slippage_modeling"],
    },
    "trend_reversal": {
        "description": "Sudden 180° price movement over 5-20 bars",
        "type": "trend",
        "severity_range": (1.5, 4.0),
        "duration_minutes_range": (5, 20),
        "affected_channels": ["trend_detection", "entry_filters"],
    },
    "spread_widening": {
        "description": "Bid-ask spread widens 5x-15x for 5-30 minutes",
        "type": "execution",
        "severity_range": (5.0, 15.0),
        "duration_minutes_range": (5, 30),
        "affected_channels": ["execution_gateway", "cost_modeling"],
    },
    "latency_spike": {
        "description": "Execution latency increases 50-500ms for 5-15 minutes",
        "type": "execution",
        "severity_range": (50, 500),
        "duration_minutes_range": (5, 15),
        "affected_channels": ["fill_modeling", "execution_gateway"],
    },
    "regime_flip": {
        "description": "Complete market regime flip (bull→bear, ranging→high_vol)",
        "type": "regime",
        "severity_range": (1.0, 1.0),
        "duration_minutes_range": (30, 120),
        "affected_channels": ["all"],
    },
    "correlation_break": {
        "description": "Cross-asset correlation structure breaks (diversification fails)",
        "type": "correlation",
        "severity_range": (1.0, 3.0),
        "duration_minutes_range": (30, 90),
        "affected_channels": ["portfolio", "risk_modeling"],
    },
    # Phase 31F — Enhanced economic survival stress perturbations
    "liquidity_drought": {
        "description": "Extended liquidity drought — volume drops 80-95% for 30-120 minutes",
        "type": "liquidity",
        "severity_range": (4.0, 8.0),
        "duration_minutes_range": (30, 120),
        "affected_channels": ["execution", "slippage_modeling", "position_sizing"],
    },
    "spread_explosion": {
        "description": "Bid-ask spread explodes 10x-25x, fills become unreliable",
        "type": "execution",
        "severity_range": (10.0, 25.0),
        "duration_minutes_range": (5, 20),
        "affected_channels": ["execution_gateway", "cost_modeling", "fill_modeling"],
    },
    "execution_degradation": {
        "description": "Fill rate drops to 30-60%, slippage increases 3x-8x",
        "type": "execution",
        "severity_range": (3.0, 8.0),
        "duration_minutes_range": (10, 45),
        "affected_channels": ["fill_modeling", "execution_gateway", "cost_modeling"],
    },
    "trend_acceleration": {
        "description": "Trend accelerates 3x-8x, momentum strategies overextend",
        "type": "trend",
        "severity_range": (3.0, 8.0),
        "duration_minutes_range": (10, 30),
        "affected_channels": ["trend_detection", "entry_filters", "exit_filters"],
    },
    "flash_crash": {
        "description": "Flash crash — 5-15% drop over 5-15 minutes, sharp reversal",
        "type": "volatility",
        "severity_range": (8.0, 15.0),
        "duration_minutes_range": (5, 15),
        "affected_channels": ["all"],
    },
    "regime_oscillation": {
        "description": "Rapid regime oscillation every 5-15 minutes for 30-90 minutes",
        "type": "regime",
        "severity_range": (1.0, 2.0),
        "duration_minutes_range": (30, 90),
        "affected_channels": ["all"],
    },
    "slippage_wave": {
        "description": "Slippage oscillates unpredictably between 1x-20x normal",
        "type": "execution",
        "severity_range": (1.0, 20.0),
        "duration_minutes_range": (15, 60),
        "affected_channels": ["execution_gateway", "cost_modeling", "slippage_modeling"],
    },
    "volume_drought": {
        "description": "Volume drops to 5-15% of normal for 60-180 minutes",
        "type": "liquidity",
        "severity_range": (6.0, 10.0),
        "duration_minutes_range": (60, 180),
        "affected_channels": ["execution", "position_sizing", "entry_filters"],
    },
}


class RegimeStressEngine(BaseAgent):
    """
    L7 Meta Agent — Synthetic market perturbation injection.

    Injects controlled environmental shocks to force regime adaptation
    and selection pressure. Does NOT modify actual market data — only
    publishes perturbation signals that downstream agents consume.

    Phase 31F adds:
      - Liquidity droughts (extended volume drops)
      - Spread explosions (10x-25x spread widening)
      - Execution degradation (fill rates drop)
      - Trend accelerations (momentum overextension)
      - Flash crashes (sudden sharp drops)
      - Regime oscillations (rapid regime flips)
      - Slippage waves (unpredictable slippage)
      - Volume droughts (extended low volume periods)
    """

    name = "RegimeStressEngine"
    agent_type = "regime_stress"
    layer = "L7"

    def __init__(self, redis_client=None, db_client=None, run_interval: int = 300):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db = db_client
        self.run_interval = run_interval

        # Active perturbations state
        self._active_perturbations: list[dict] = []
        self._perturbation_history: list[dict] = []
        self._organism_collapse_log: list[dict] = []
        self._organism_survival_log: list[dict] = []

        # Phase 31F: Stress cycle tracking
        self._total_stress_cycles = 0
        self._total_collapses_observed = 0
        self._total_survivors_observed = 0

        # Probability of injecting a perturbation each cycle
        self.PERTURBATION_PROBABILITY = 0.40  # Slightly higher in Phase 31F

        # Maximum concurrent perturbations
        self.MAX_CONCURRENT_PERTURBATIONS = 4  # More concurrent stress in Phase 31F

        # Phase 31F: Stress severity amplification
        self.STRESS_AMPLIFICATION_FACTOR = 1.0

    async def run(self):
        logger.info(
            f"{self.name}: starting regime stress engineering (Phase 31F enhanced — every {self.run_interval}s)"
        )
        while self.status == "running":
            try:
                await self._stress_cycle()
                self._total_stress_cycles += 1
            except Exception as e:
                logger.error(f"{self.name}: stress cycle failed: {e}")
            await asyncio.sleep(self.run_interval)

    async def _stress_cycle(self):
        """Full stress cycle: expire + inject + evaluate + persist + notify."""
        # 1. Expire old perturbations
        self._expire_perturbations()

        # 2. Inject new perturbations if space available
        n_new = 0
        space_available = self.MAX_CONCURRENT_PERTURBATIONS - len(self._active_perturbations)
        for _ in range(space_available):
            if random.random() < self.PERTURBATION_PROBABILITY:
                # Phase 31F: More severe perturbations over time
                self.STRESS_AMPLIFICATION_FACTOR = min(2.0, 1.0 + self._total_stress_cycles * 0.05)
                perturbation = self._generate_perturbation()
                if perturbation:
                    self._active_perturbations.append(perturbation)
                    n_new += 1
                    logger.info(
                        f"{self.name}: Injected {perturbation['type']} "
                        f"(severity={perturbation['severity']:.2f}, "
                        f"duration={perturbation['duration_minutes']}m, "
                        f"amplification={self.STRESS_AMPLIFICATION_FACTOR:.1f}x)"
                    )

        # 3. Evaluate resilience of active strategies against perturbations
        resilience = await self._evaluate_resilience()

        # 4. Observe organism collapse/survival under stress
        collapse_observations = await self._observe_stress_effects()

        # 5. Persist state
        await self._persist_state(
            perturbations=self._active_perturbations,
            resilience=resilience,
            collapse_observations=collapse_observations,
        )

        # 6. Publish to Redis
        await self._publish_state()

        # Log summary
        if self._active_perturbations:
            types = [p['type'] for p in self._active_perturbations]
            categories = [p.get('category', 'unknown') for p in self._active_perturbations]
            logger.info(
                f"{self.name}: {len(self._active_perturbations)} active perturbations: "
                f"types={types}, categories={set(categories)}"
            )
        else:
            logger.debug(f"{self.name}: No active perturbations")

    def _expire_perturbations(self):
        """Remove perturbations that have exceeded their duration."""
        now = datetime.now(timezone.utc)
        still_active = []
        for p in self._active_perturbations:
            started = p["started_at"]
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            elapsed_minutes = (now - started).total_seconds() / 60.0
            if elapsed_minutes < p["duration_minutes"]:
                still_active.append(p)
            else:
                logger.info(
                    f"{self.name}: Expired {p['type']} perturbation "
                    f"(lasted {elapsed_minutes:.1f}m/{p['duration_minutes']}m)"
                )
                self._perturbation_history.append({**p, "expired_at": now.isoformat()})
        self._active_perturbations = still_active

    def _generate_perturbation(self) -> Optional[dict]:
        """Generate a random perturbation from the presets, with Phase 31F amplification."""
        preset_name = random.choice(list(PERTURBATION_PRESETS.keys()))
        preset = PERTURBATION_PRESETS[preset_name]

        # Apply Phase 31F amplification
        severity_raw = random.uniform(preset["severity_range"][0], preset["severity_range"][1])
        severity = round(severity_raw * self.STRESS_AMPLIFICATION_FACTOR, 2)
        duration = random.randint(
            preset["duration_minutes_range"][0], preset["duration_minutes_range"][1]
        )

        # Pick a random target symbol
        symbols = ["BTCUSDT", "ETHUSDT", "SPY", "QQQ", "NVDA", "AAPL", "MSFT", "SOLUSDT"]
        target_symbol = random.choice(symbols)

        perturbation = {
            "id": str(uuid.uuid4())[:8],
            "type": preset_name,
            "category": preset["type"],
            "description": preset["description"],
            "severity": severity,
            "duration_minutes": duration,
            "target_symbol": target_symbol,
            "started_at": datetime.now(timezone.utc),
            "affected_channels": preset["affected_channels"],
            "amplification_factor": self.STRESS_AMPLIFICATION_FACTOR,
            "stress_cycle": self._total_stress_cycles,
        }

        return perturbation

    async def _evaluate_resilience(self) -> dict:
        """Evaluate how well active strategies survive under current perturbations."""
        if not self._active_perturbations or not self.db:
            return {}

        # Get active strategies
        try:
            async with self.db.engine.connect() as conn:
                result = await conn.execute(
                    text("""
                        SELECT s.id, s.name, b.composite_fitness_score,
                               b.sharpe, b.max_drawdown, b.total_trades,
                               b.win_rate, b.results
                        FROM strategies s
                        JOIN backtest_results b ON s.id = b.strategy_id
                        WHERE s.status IN ('validated', 'elite', 'promoted', 'live')
                          AND b.composite_fitness_score IS NOT NULL
                        ORDER BY b.composite_fitness_score DESC
                        LIMIT 50
                    """)
                )
                strategies = result.fetchall()
        except Exception as e:
            logger.warning(f"{self.name}: fetch strategies for resilience failed: {e}")
            return {}

        if not strategies:
            return {}

        # Compute aggregate stress level from all active perturbations
        stress_level = min(1.0, sum(
            p.get("severity", 1.0) / 10.0 for p in self._active_perturbations
        ) / max(1, len(self._active_perturbations)))
        stress_level = min(1.0, stress_level)
        n_perturbations = len(self._active_perturbations)

        # Per-strategy resilience scoring
        strategy_resilience = {}
        for s in strategies:
            sid = str(s[0])
            composite = float(s[2]) if s[2] else 0
            sharpe = float(s[3]) if s[3] else 0
            max_dd = float(s[4]) if s[4] else 0
            trades = int(s[5]) if s[5] else 0
            win_rate = float(s[6]) if s[6] else 0
            # Extract profit_factor from JSONB results column
            results_raw = s[7]
            if isinstance(results_raw, str):
                try:
                    results_raw = json.loads(results_raw)
                except Exception:
                    results_raw = {}
            elif results_raw is None:
                results_raw = {}
            profit_factor = float(results_raw.get("profit_factor", 1.0))

            # Phase 31F: Multi-factor resilience scoring
            # - Higher win rate → more resilient (consistent)
            # - Lower drawdown → more resilient
            # - Higher trades → more statistically robust
            # - Higher profit_factor → more capital efficient
            # - Higher sharpe → better risk-adjusted returns
            resilience_score = (
                win_rate * 0.20
                + (1.0 - min(1.0, max_dd / 40)) * 0.25
                + min(1.0, trades / 50) * 0.20
                + min(1.0, profit_factor / 3.0) * 0.20
                + min(1.0, max(0, sharpe) / 2.0) * 0.15
            )

            # Phase 31F: Stress penalty scales with number and severity of perturbations
            perturbation_penalty = min(0.5, n_perturbations * 0.1 * stress_level)
            stressed_score = composite * (1.0 - perturbation_penalty)

            # Classify resilience level
            if resilience_score > 0.6:
                resilience_level = "resilient"
            elif resilience_score > 0.35:
                resilience_level = "moderate"
            else:
                resilience_level = "fragile"

            strategy_resilience[sid] = {
                "name": s[1],
                "composite_score": round(composite, 2),
                "resilience_score": round(resilience_score, 4),
                "resilience_level": resilience_level,
                "stressed_score": round(stressed_score, 2),
                "stress_penalty": round(perturbation_penalty, 4),
                "win_rate": round(win_rate, 4),
                "max_drawdown": round(max_dd, 2),
                "total_trades": trades,
                "profit_factor": round(profit_factor, 2),
                "sharpe": round(sharpe, 2),
            }

        # Compute aggregate stats
        resilience_values = [r["resilience_score"] for r in strategy_resilience.values()]
        n_resilient = sum(1 for r in strategy_resilience.values() if r["resilience_level"] == "resilient")
        n_fragile = sum(1 for r in strategy_resilience.values() if r["resilience_level"] == "fragile")

        return {
            "assessed_at": datetime.now(timezone.utc).isoformat(),
            "active_perturbations": n_perturbations,
            "stress_level": round(stress_level, 4),
            "strategies_assessed": len(strategy_resilience),
            "avg_resilience": round(float(np.mean(resilience_values)), 4) if resilience_values else 0,
            "min_resilience": round(float(np.min(resilience_values)), 4) if resilience_values else 0,
            "max_resilience": round(float(np.max(resilience_values)), 4) if resilience_values else 0,
            "n_resilient": n_resilient,
            "n_fragile": n_fragile,
            "strategy_resilience": strategy_resilience,
        }

    async def _observe_stress_effects(self) -> dict:
        """Observe which organisms collapse and which survive under stress.

        Uses CTE for avg fitness to avoid Postgres GROUP BY restriction on
        correlated subqueries inside aggregate queries.
        """
        if not self.db:
            return {}

        try:
            async with self.db.engine.connect() as conn:
                # Get recently created vs retired strategies
                result = await conn.execute(text("""
                    WITH latest_fitness AS (
                        SELECT DISTINCT ON (br.strategy_id)
                            br.strategy_id,
                            br.composite_fitness_score
                        FROM backtest_results br
                        ORDER BY br.strategy_id, br.created_at DESC
                    )
                    SELECT
                        COALESCE(COUNT(*) FILTER (
                            WHERE s.created_at > NOW() - INTERVAL '1 hour'
                        ), 0) AS newborns,
                        COALESCE(COUNT(*) FILTER (
                            WHERE s.lifecycle_state = 'retired'
                            AND s.created_at > NOW() - INTERVAL '1 hour'
                        ), 0) AS recently_retired,
                        COALESCE(COUNT(*) FILTER (
                            WHERE s.lifecycle_state IN ('degrading', 'quarantined')
                        ), 0) AS degrading,
                        COALESCE(AVG(lf.composite_fitness_score), 0) AS avg_fitness
                    FROM strategies s
                    LEFT JOIN latest_fitness lf ON lf.strategy_id = s.id
                """))
                row = result.fetchone()

                obs = {
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "newborns_intra_hour": int(row[0]) if row else 0,
                    "recently_retired_intra_hour": int(row[1]) if row else 0,
                    "currently_degrading": int(row[2]) if row else 0,
                    "avg_fitness": round(float(row[3] or 0), 2) if row else 0,
                    "active_perturbations": len(self._active_perturbations),
                    "stress_cycle": self._total_stress_cycles,
                }

                # Track survivors vs collapsed
                if row and int(row[1]) > 0:
                    self._total_collapses_observed += int(row[1])
                if row:
                    self._total_survivors_observed = max(
                        self._total_survivors_observed,
                        int(row[0]) - int(row[1]),
                    )

                return obs
        except Exception as e:
            logger.warning(f"{self.name}: observe stress effects failed: {e}")
            return {}

    async def _persist_state(self, perturbations: list[dict], resilience: dict, collapse_observations: dict):
        """Persist perturbation events, resilience assessments, and stress observations."""
        if not self.db:
            return

        # Persist each active perturbation
        for p in perturbations:
            try:
                await self.db._execute_insert(
                    """
                    INSERT INTO regime_perturbation_events
                        (perturbation_type, severity,
                         started_at, status, metadata)
                    VALUES
                        (:ptype, :severity,
                         :started_at, 'active', CAST(:metadata AS jsonb))
                    """,
                    {
                        "ptype": p["type"],
                        "severity": p["severity"],
                        "started_at": p["started_at"],
                        "metadata": json.dumps({
                            "category": p.get("category", p["type"]),
                            "duration_minutes": p["duration_minutes"],
                            "target_symbol": p["target_symbol"],
                            "affected_channels": p["affected_channels"],
                            "amplification_factor": p.get("amplification_factor", 1.0),
                            "stress_cycle": p.get("stress_cycle", 0),
                            "description": p.get("description", ""),
                        }),
                    },
                )
            except Exception as e:
                logger.warning(f"{self.name}: persist perturbation failed: {e}")

        # Persist resilience assessment
        if resilience:
            try:
                await self.db._execute_insert(
                    """
                    INSERT INTO regime_perturbation_events
                        (perturbation_type, severity,
                         status, metadata)
                    VALUES
                        (:ptype, :severity,
                         'completed', CAST(:meta AS jsonb))
                    """,
                    {
                        "ptype": "resilience_assessment",
                        "severity": resilience.get("stress_level", 0),
                        "meta": json.dumps({
                            "category": "assessment",
                            "resilience_data": resilience,
                        }),
                    },
                )
            except Exception as e:
                logger.warning(f"{self.name}: persist resilience failed: {e}")

        # Phase 31F: Persist collapse/survival observations
        if collapse_observations:
            try:
                await self.db._execute_insert(
                    """
                    INSERT INTO regime_perturbation_events
                        (perturbation_type, severity,
                         status, metadata)
                    VALUES
                        (:ptype, :severity,
                         'completed', CAST(:meta AS jsonb))
                    """,
                    {
                        "ptype": "stress_observation",
                        "severity": collapse_observations.get("active_perturbations", 0) / max(1, self.MAX_CONCURRENT_PERTURBATIONS),
                        "meta": json.dumps({
                            "category": "observation",
                            "observations": collapse_observations,
                        }),
                    },
                )
            except Exception as e:
                logger.warning(f"{self.name}: persist stress observation failed: {e}")

    async def _publish_state(self):
        """Publish active perturbations and resilience to Redis."""
        if not self._redis:
            return
        try:
            state = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_perturbations": [
                    {
                        "type": p["type"],
                        "category": p.get("category", p["type"]),
                        "severity": p["severity"],
                        "duration_minutes": p["duration_minutes"],
                        "target_symbol": p["target_symbol"],
                        "affected_channels": p["affected_channels"],
                    }
                    for p in self._active_perturbations
                ],
                "n_active": len(self._active_perturbations),
                "stress_cycle": self._total_stress_cycles,
                "total_collapses_observed": self._total_collapses_observed,
            }
            await self._redis.set(
                "regime_stress:current",
                json.dumps(state),
                ex=self.run_interval + 30,
            )
        except Exception as e:
            logger.warning(f"{self.name}: publish failed: {e}")

    # ─────────────────────────────────────────────────────────
    # PUBLIC METHODS — for downstream consumers
    # ─────────────────────────────────────────────────────────

    async def get_active_perturbations(self) -> list[dict]:
        """Return all currently active perturbations."""
        return list(self._active_perturbations)

    async def is_symbol_stressed(self, symbol: str) -> bool:
        """Check if a symbol is currently under any perturbation."""
        for p in self._active_perturbations:
            if p.get("target_symbol") == symbol:
                return True
        return False

    async def get_regime_stress_factor(self, channel: str) -> float:
        """
        Get combined stress multiplier for a given channel.
        Returns 1.0 (no stress) to 10.0+ (extreme stress).
        """
        factor = 1.0
        for p in self._active_perturbations:
            if "all" in p.get("affected_channels", []) or channel in p.get("affected_channels", []):
                factor *= 1.0 + (p.get("severity", 1.0) - 1.0) * 0.3
        return min(10.0, factor)

    async def get_stress_summary(self) -> dict:
        """Get a comprehensive summary of current stress state."""
        return {
            "active_perturbations": len(self._active_perturbations),
            "perturbation_types": [p["type"] for p in self._active_perturbations],
            "stress_cycles_completed": self._total_stress_cycles,
            "total_collapses_observed": self._total_collapses_observed,
            "total_survivors_observed": self._total_survivors_observed,
            "amplification_factor": self.STRESS_AMPLIFICATION_FACTOR,
            "max_concurrent": self.MAX_CONCURRENT_PERTURBATIONS,
            "stress_history_size": len(self._perturbation_history),
        }

    async def get_collapse_survival_ratio(self) -> float:
        """Get the ratio of collapses to survivors (higher = more stressful)."""
        total = self._total_collapses_observed + self._total_survivors_observed
        if total == 0:
            return 0.0
        return self._total_collapses_observed / total
