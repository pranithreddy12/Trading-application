import asyncio
import json
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


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
  rsi_14, macd, macd_signal, ema_12, ema_26, sma_20,
  bollinger_upper, bollinger_lower, vwap,
  returns, close, volume,
  price_vs_vwap_pct, ema_spread_pct,
  relative_volume, bollinger_band_position,
  volatility_regime, trend_strength

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
            top_strategies = await self.db_client.get_top_strategies_by_composite_score(
                0.0, 100.0, 10
            )

            if len(top_strategies) < 2:
                logger.info("Not enough strategies to combine — skipping")
                return

            # Find an untried pair
            import itertools
            untried_pair = None
            for a, b in itertools.combinations(top_strategies, 2):
                exists = await self.db_client.check_combination_exists(
                    a["id"], b["id"]
                )
                if not exists:
                    untried_pair = (a, b)
                    break

            if untried_pair is None:
                logger.info("All top pairs already combined — skipping")
                return

            strat1, strat2 = untried_pair
            logger.info(
                f"Combining: {strat1['name']} + {strat2['name']}"
            )

            user_prompt = f"""Combine these two strategies into a superior hybrid:

Strategy A: {strat1['name']}
Score: {strat1.get('short_window_score', 'N/A')}
Spec: {json.dumps(strat1.get('parameters', {}), indent=2)}

Strategy B: {strat2['name']}
Score: {strat2.get('short_window_score', 'N/A')}
Spec: {json.dumps(strat2.get('parameters', {}), indent=2)}

Create a hybrid that uses the best entry logic from A
and the best exit logic from B (or vice versa).
Ensure conditions use ONLY approved feature names."""

            # Use urllib-based client — no httpx
            raw = await _claude.complete(
                user=user_prompt,
                system=self.SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.7,
            )

            logger.info(f"CombinerAgent Claude response:\n{raw[:400]}")

            # Extract JSON
            cleaned = raw.strip()
            if "```" in cleaned:
                start = cleaned.find("\n", cleaned.find("```")) + 1
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()
            f = cleaned.find("{")
            l = cleaned.rfind("}")
            if f == -1:
                raise ValueError("No JSON in Claude response")

            hybrid_spec = json.loads(cleaned[f:l+1])

            # Save hybrid strategy
            strategy_id = await self.db_client.save_strategy(
                hybrid_spec,
                status="pending_code",
                author_agent=self.name,
            )

            # Record the combination lineage
            await self.db_client.save_combination_record(
                parent_a=strat1["id"],
                parent_b=strat2["id"],
                child_id=strategy_id,
                combination_type="claude_hybrid",
                parent_a_score=strat1.get("short_window_score", 0),
                parent_b_score=strat2.get("short_window_score", 0),
            )

            # Notify pipeline
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