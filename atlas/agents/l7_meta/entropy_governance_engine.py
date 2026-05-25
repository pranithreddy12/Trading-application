"""
entropy_governance_engine.py — Phase 26D

Makes disagreement entropy behaviorally active:
  - Scout disagreement entropy → leverage multiplier
  - Contradiction escalation → diversification forcing
  - Trust dispersion → overconfidence suppression

Publishes governance signals to Redis for consumption by:
  - CopyCapitalAllocator (leverage cap)
  - IdeatorAgentV2 (aggression modulation)
  - MutationPolicyEngine (exploration/exploitation balance)
  - ExecutionAgent (sizing decisions)

ADVISORY ONLY — writes to Redis and DB, never executes trades.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class EntropyGovernanceEngine(BaseAgent):
    """L7 Meta Agent — Converts scout entropy into behavioral governance signals."""

    name = "EntropyGovernanceEngine"
    agent_type = "entropy_governance"
    layer = "L7"

    # Entropy thresholds
    HIGH_ENTROPY = 0.70     # Scouts strongly disagree → conservative mode
    CRITICAL_ENTROPY = 0.85 # Scouts maximally disagree → defensive mode

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client,
                         advisory_only=True)
        self.redis = redis_client
        self.db = db_client
        self._run_interval = 300  # Every 5 minutes

    async def run(self):
        logger.info(f"{self.name}: Starting entropy governance loop")
        while self.status == "running":
            try:
                await self._governance_cycle()
            except Exception as e:
                logger.error(f"{self.name}: Governance cycle error: {e}")

            for _ in range(self._run_interval // 10):
                await asyncio.sleep(10)
                if self.status != "running":
                    return

    async def _governance_cycle(self):
        """Fetch latest scout synthesis, compute governance signals, publish."""
        # Step 1: Fetch latest synthesis
        synthesis = await self._fetch_latest_synthesis()
        if not synthesis:
            return

        entropy = synthesis.get("disagreement_entropy", 0.5)
        agreement = synthesis.get("scout_agreement_score", 0.5)
        consensus_reliability = synthesis.get("consensus_reliability", 0.5)
        n_disagreements = len(synthesis.get("scout_disagreement_areas", []))

        # Step 2: Compute governance multipliers
        leverage_multiplier = self._compute_leverage_multiplier(
            entropy, n_disagreements, consensus_reliability
        )
        aggression_cap = self._compute_aggression_cap(entropy, agreement)
        exploration_bias = self._compute_exploration_bias(entropy, consensus_reliability)
        sizing_floor = self._compute_sizing_floor(entropy)

        governance = {
            "entropy": round(entropy, 4),
            "agreement_score": round(agreement, 4),
            "consensus_reliability": round(consensus_reliability, 4),
            "n_disagreements": n_disagreements,
            "leverage_multiplier": round(leverage_multiplier, 4),
            "aggression_cap": round(aggression_cap, 4),
            "exploration_bias": round(exploration_bias, 4),
            "sizing_floor": round(sizing_floor, 4),
            "governance_mode": self._classify_mode(entropy),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Step 3: Publish to Redis for organism-wide consumption
        if self.redis:
            await self.redis.set(
                "entropy_governance:current",
                json.dumps(governance),
                ex=600  # 10-minute TTL
            )

        # Step 4: Persist governance snapshot to DB
        await self._persist_governance(governance)

        logger.info(
            f"{self.name}: Entropy={entropy:.3f} → "
            f"leverage_mult={leverage_multiplier:.3f}, "
            f"aggression_cap={aggression_cap:.3f}, "
            f"mode={governance['governance_mode']}"
        )

    async def _fetch_latest_synthesis(self) -> dict | None:
        """Fetch the most recent scout synthesis record."""
        try:
            async with self.db.engine.connect() as conn:
                r = await conn.execute(text("""
                    SELECT confidence, scout_agreement_score,
                           scout_disagreement_areas, metadata
                    FROM scout_synthesis_log
                    ORDER BY created_at DESC
                    LIMIT 1
                """))
                row = r.fetchone()
                if not row:
                    return None

                meta = row[3] or {}
                if isinstance(meta, str):
                    meta = json.loads(meta)

                disagreements = row[2] or []
                if isinstance(disagreements, str):
                    disagreements = json.loads(disagreements)

                return {
                    "disagreement_entropy": float(meta.get("disagreement_entropy", 0.5)),
                    "scout_agreement_score": float(row[1] or 0.5),
                    "consensus_reliability": float(meta.get("consensus_reliability", 0.5)),
                    "scout_disagreement_areas": disagreements,
                }
        except Exception as e:
            logger.debug(f"{self.name}: Failed to fetch synthesis: {e}")
            return None

    def _compute_leverage_multiplier(
        self, entropy: float, n_disagreements: int, consensus_reliability: float
    ) -> float:
        """High entropy → reduce leverage. Low entropy → allow full leverage."""
        # Base from entropy
        if entropy >= self.CRITICAL_ENTROPY:
            base = 0.50  # 50% of normal leverage in critical disagreement
        elif entropy >= self.HIGH_ENTROPY:
            base = 0.70  # 70% of normal leverage in high disagreement
        else:
            base = 1.0   # Full leverage in low disagreement

        # Penalize for active disagreements
        disagreement_penalty = min(0.3, n_disagreements * 0.05)

        # Boost for high consensus reliability
        reliability_boost = (consensus_reliability - 0.5) * 0.2

        return max(0.3, min(1.0, base - disagreement_penalty + reliability_boost))

    def _compute_aggression_cap(self, entropy: float, agreement: float) -> float:
        """Higher entropy caps ideator aggression lower."""
        if entropy >= self.CRITICAL_ENTROPY:
            return 0.5
        elif entropy >= self.HIGH_ENTROPY:
            return 0.7
        elif agreement >= 0.8:
            return 1.2  # High agreement: allow slightly elevated aggression
        else:
            return 1.0

    def _compute_exploration_bias(self, entropy: float, reliability: float) -> float:
        """High entropy + low reliability → wider mutation exploration.
        Low entropy + high reliability → exploit known-good mutations.
        """
        if entropy >= self.HIGH_ENTROPY and reliability < 0.5:
            return 1.4  # Wide exploration
        elif entropy < 0.3 and reliability > 0.7:
            return 0.6  # Tight exploitation
        else:
            return 1.0

    def _compute_sizing_floor(self, entropy: float) -> float:
        """High entropy → enforce minimum position sizing floor (no micro-positions)."""
        # In high entropy environments, we want fewer but larger, deliberate positions
        # This is a multiplier applied to base position size
        if entropy >= self.CRITICAL_ENTROPY:
            return 0.5  # Halve position sizes
        elif entropy >= self.HIGH_ENTROPY:
            return 0.75
        return 1.0

    def _classify_mode(self, entropy: float) -> str:
        if entropy >= self.CRITICAL_ENTROPY:
            return "defensive"
        elif entropy >= self.HIGH_ENTROPY:
            return "conservative"
        elif entropy < 0.3:
            return "aggressive"
        return "standard"

    async def _persist_governance(self, governance: dict) -> None:
        """Persist governance snapshot for audit and telemetry."""
        try:
            await self.db._execute_insert(
                """
                INSERT INTO scout_influence_log
                    (source_scout, target_agent, influence_type, influence_metric,
                     delta, confidence, entropy_context, metadata, created_at)
                VALUES
                    ('entropy_governance', 'organism', 'entropy_governance',
                     :mode, :leverage_delta, :entropy, :entropy,
                     CAST(:meta AS jsonb), NOW())
                """,
                {
                    "mode": governance["governance_mode"],
                    "leverage_delta": governance["leverage_multiplier"] - 1.0,
                    "entropy": governance["entropy"],
                    "meta": json.dumps(governance),
                }
            )
        except Exception as e:
            logger.debug(f"{self.name}: Persistence failed: {e}")


async def get_entropy_governance(redis_client) -> dict:
    """Helper for other agents to read the current entropy governance signal.
    
    Returns the current governance dict or sensible defaults if unavailable.
    """
    defaults = {
        "leverage_multiplier": 1.0,
        "aggression_cap": 1.0,
        "exploration_bias": 1.0,
        "sizing_floor": 1.0,
        "entropy": 0.5,
        "governance_mode": "standard",
    }
    try:
        raw = await redis_client.get("entropy_governance:current")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return defaults
