import asyncio
import json
import re
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.messaging import MessagingClient, Channel
from atlas.core.selection import tournament_select_unique
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.viability_score import (
    compute_viability_score,
    classify_viability,
)
from atlas.agents.l2_strategy.strategy_normalizer import KNOWN_FEATURES
from atlas.agents.l2_strategy.mutator_agent import (
    standardized_similarity,
    _is_duplicate,
)


MIN_VIABILITY = 0.3


def _validate_hybrid(spec: dict) -> str | None:
    """Structural validation before saving a hybrid. Returns error string or None."""
    entry = spec.get("entry_conditions", [])
    exit_ = spec.get("exit_conditions", [])
    if not entry and not exit_:
        return "No entry or exit conditions"
    if len(entry) == 0:
        return "Zero entry conditions"
    if len(entry) > 3:
        return f"Too many entry conditions ({len(entry)} > 3)"
    return None


def _check_features(spec: dict) -> str | None:
    """Reject conditions referencing features not in the approved KNOWN_FEATURES registry."""
    features = set()
    for key in ("entry_conditions", "exit_conditions"):
        for cond in spec.get(key) or []:
            for feat in re.findall(r"\b[a-z_][a-z_0-9]*\b", str(cond)):
                features.add(feat)
    unknown = features - KNOWN_FEATURES
    if unknown:
        return f"Unknown features: {', '.join(sorted(unknown))}"
    return None


class CombinerAgent(BaseAgent):
    """
    Combines two top-performing strategies into a hybrid using Claude.
    Runs every 2 hours automatically.
    Uses urllib-based ClaudeClient — httpx is network-blocked.
    """

    RUN_INTERVAL_SECONDS = 7200  # 2 hours

    SYSTEM_PROMPT = """You are a quantitative strategist for Shah Quantum Fund.
Combine two trading strategies into a superior hybrid.
Preserve the strengths of both and minimize weaknesses.

APPROVED FEATURES (use ONLY these exact names):
  rsi_14, macd, macd_signal, sma_5, sma_20,
  ema_12, ema_26, vwap,
  bollinger_upper, bollinger_lower,
  returns, log_returns, close, open, high, low, volume,
  price_vs_vwap_pct, ema_spread_pct,
  relative_volume, bollinger_band_position,
  volatility_regime, trend_strength, rolling_volatility

Conditions must be pure boolean comparisons: feature operator value
No natural language. No English prose in conditions.

Respond with ONLY valid JSON:
{
  "strategy_name": "unique_snake_case_name",
  "hypothesis": "one sentence",
  "entry_conditions": ["feature > value", "feature < value"],
  "exit_conditions": ["feature > value"],
  "stop_loss": "0.5% below entry",
  "take_profit": "1.0% above entry",
  "position_sizing": "10% of portfolio",
  "timeframe": "1m",
  "asset_class": "equity or crypto",
  "expected_sharpe": 1.2,
  "expected_win_rate": 0.52,
  "risk_level": "medium",
  "tags": ["combined"]
}"""

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name="CombinerAgent",
            agent_type="combiner",
            layer="L2",
            redis_client=redis_client,
        )
        self.db_client = db_client

    async def run(self):
        logger.info("CombinerAgent started — runs every 2 hours")
        while self.status == "running":
            await self._combine_top_strategies()
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _combine_top_strategies(self):
        try:
            candidate_pool = await self.db_client.get_top_strategies_by_composite_score(
                0.0, 100.0, 30
            )

            if len(candidate_pool) < 2:
                logger.info("Not enough strategies to combine — skipping")
                return

            max_attempts = 10
            strat1 = None
            strat2 = None

            for _ in range(max_attempts):
                selected = tournament_select_unique(
                    candidate_pool,
                    tournament_size=5,
                    key="composite_score",
                    n_select=2,
                    id_key="id",
                )
                if len(selected) < 2:
                    continue

                a, b = selected[0], selected[1]
                exists = await self.db_client.check_combination_exists(a["id"], b["id"])
                if not exists:
                    strat1, strat2 = a, b
                    break

            if strat1 is None or strat2 is None:
                logger.info(
                    "No untried pair found after tournament attempts — skipping"
                )
                return
            logger.info(f"Combining: {strat1['name']} + {strat2['name']}")

            user_prompt = f"""Combine these two strategies into a superior hybrid:

Strategy A: {strat1["name"]}
Score: {strat1.get("composite_score", "N/A")}
Spec: {json.dumps(strat1.get("parameters", {}), indent=2)}

Strategy B: {strat2["name"]}
Score: {strat2.get("composite_score", "N/A")}
Spec: {json.dumps(strat2.get("parameters", {}), indent=2)}

Create a hybrid that uses the best entry logic from A
and the best exit logic from B (or vice versa).
Ensure conditions use ONLY approved feature names."""

            raw = await _claude.complete(
                user=user_prompt,
                system=self.SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.4,
            )

            logger.info(f"CombinerAgent Claude response:\n{raw[:400]}")

            cleaned = raw.strip()
            if "```" in cleaned:
                start = cleaned.find("\n", cleaned.find("```")) + 1
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()
            f = cleaned.find("{")
            l = cleaned.rfind("}")
            if f == -1:
                raise ValueError("No JSON in Claude response")

            hybrid_spec = json.loads(cleaned[f : l + 1])

            # ---- Validation gates ----

            # 1. Structural validation
            error = _validate_hybrid(hybrid_spec)
            if error:
                logger.warning(f"CombinerAgent: Structural validation failed: {error}")
                return

            # 2. Feature registry enforcement
            error = _check_features(hybrid_spec)
            if error:
                logger.warning(f"CombinerAgent: Feature check failed: {error}")
                return

            # 3. Viability gate
            viability = compute_viability_score(
                hybrid_spec,
                parent_params=strat1.get("parameters", {}),
            )
            viability_class = classify_viability(viability)
            if viability < MIN_VIABILITY:
                logger.warning(
                    f"CombinerAgent: Low viability {viability:.3f} ({viability_class}) — rejecting"
                )
                return
            logger.info(f"CombinerAgent: Viability {viability:.3f} ({viability_class})")

            # 4. Anti-clone check
            existing_specs = []
            for s in [strat1, strat2]:
                if s.get("parameters"):
                    existing_specs.append(s["parameters"])
            for s in candidate_pool:
                if s.get("parameters") and s["id"] not in (strat1["id"], strat2["id"]):
                    existing_specs.append(s["parameters"])
            if _is_duplicate(hybrid_spec, existing_specs):
                logger.warning(
                    "CombinerAgent: Hybrid too similar to existing — rejecting"
                )
                return

            # ---- Save ----

            strategy_id = await self.db_client.save_strategy(
                hybrid_spec,
                status="pending_code",
                author_agent=self.name,
            )

            await self.db_client.save_combination_record(
                parent_a=strat1["id"],
                parent_b=strat2["id"],
                child_id=strategy_id,
                combination_type="claude_hybrid",
                parent_a_score=strat1.get("composite_score", 0),
                parent_b_score=strat2.get("composite_score", 0),
            )

            messaging = MessagingClient(self._redis)
            await messaging.publish(
                Channel.STRATEGY_SIGNALS,
                {"type": "new_spec", "strategy_id": strategy_id},
            )

            logger.info(
                f"CombinerAgent: ✅ Hybrid saved [{strategy_id}] "
                f"from {strat1['name']} + {strat2['name']}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"CombinerAgent: JSON parse error: {e}")
        except Exception as e:
            logger.error(f"CombinerAgent: Error: {type(e).__name__}: {e}")
