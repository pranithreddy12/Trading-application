import asyncio
import json
from loguru import logger
from redis.asyncio import Redis
from anthropic import AsyncAnthropic

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


class CombinerAgent(BaseAgent):
    """
    Combines two top-performing strategies into a hybrid using Claude.
    Runs every 2 hours automatically.
    """

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name="CombinerAgent",
            agent_type="combiner",
            layer="L2",
            redis_client=redis_client,
        )
        self.RUN_INTERVAL_SECONDS = 7200  # 2 hours
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.db_client = db_client

    async def run(self):
        while self.status == "running":
            await self._combine_top_strategies()
            await asyncio.sleep(self.RUN_INTERVAL_SECONDS)

    async def _combine_top_strategies(self):
        try:
            top_strategies = await self.db_client.get_top_strategies_by_composite_score(
                0.0, 100.0, 10
            )

            if len(top_strategies) < 2:
                logger.info(
                    "Not enough strategies with temporal scores to combine. Skipping."
                )
                return

            import itertools

            untried_pair = None
            for a, b in itertools.combinations(top_strategies, 2):
                exists = await self.db_client.check_combination_exists(a["id"], b["id"])
                if not exists:
                    untried_pair = (a, b)
                    break

            if untried_pair is None:
                logger.info("All pairs in top pool already combined. Skipping.")
                return

            strat1, strat2 = untried_pair

            SYSTEM_PROMPT = """
You are a quantitative strategist for Shah Quantum Fund.
Combine two trading strategies into a superior hybrid.
The hybrid must preserve the strengths of both and minimize weaknesses.
Respond with ONLY the strategy JSON in the exact same format as before:
{
  "strategy_name": "...",
  "hypothesis": "...",
  "entry_conditions": [],
  "exit_conditions": [],
  "stop_loss": "...",
  "take_profit": "...",
  "position_sizing": "...",
  "timeframe": "...",
  "asset_class": "...",
  "expected_sharpe": 1.5,
  "expected_win_rate": 0.55,
  "risk_level": "...",
  "tags": []
}
"""
            user_prompt = f"""
Strategy 1: {strat1["name"]} (Temporal Score: {strat1["short_window_score"]})
Spec: {json.dumps(strat1["parameters"], indent=2)}

Strategy 2: {strat2["name"]} (Temporal Score: {strat2["short_window_score"]})
Spec: {json.dumps(strat2["parameters"], indent=2)}
"""
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.7,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text

            try:
                hybrid_spec = json.loads(content)
                strategy_id = await self.db_client.save_strategy(
                    hybrid_spec, status="pending_code", author_agent=self.name
                )

                await self.db_client.save_combination_record(
                    parent_a=strat1["id"],
                    parent_b=strat2["id"],
                    child_id=strategy_id,
                    combination_type="claude_hybrid",
                    parent_a_score=strat1.get("short_window_score", 0),
                    parent_b_score=strat2.get("short_window_score", 0),
                )

                messaging = MessagingClient(self._redis)
                await messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {"type": "new_spec", "strategy_id": strategy_id},
                )
                logger.info(
                    f"Generated hybrid strategy {strategy_id} from "
                    f"{strat1['name']} ({strat1['short_window_score']}) and "
                    f"{strat2['name']} ({strat2['short_window_score']})"
                )

            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse error from Combiner Claude: {e}")

        except Exception as e:
            logger.error(f"Combine strategies error: {e}")
