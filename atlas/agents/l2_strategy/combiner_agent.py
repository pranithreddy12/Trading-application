import asyncio
import json
import random
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
            redis_client=redis_client
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
            top_strategies = await self.db_client.get_top_strategies_by_sharpe(0.0, 100.0, 5)
            
            if len(top_strategies) < 2:
                logger.info("Not enough validated strategies to combine. Skipping.")
                return
                
            strat1, strat2 = random.sample(top_strategies, 2)
            
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
Strategy 1: {strat1['name']} (Sharpe: {strat1['sharpe']})
Spec: {json.dumps(strat1['parameters'], indent=2)}

Strategy 2: {strat2['name']} (Sharpe: {strat2['sharpe']})
Spec: {json.dumps(strat2['parameters'], indent=2)}
"""
            
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.7,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )
            content = response.content[0].text
            
            try:
                hybrid_spec = json.loads(content)
                strategy_id = await self.db_client.save_strategy(
                    hybrid_spec,
                    status="pending_code",
                    author_agent=self.name
                )
                
                messaging = MessagingClient(self._redis)
                await messaging.publish(Channel.STRATEGY_SIGNALS, {
                    "type": "new_spec",
                    "strategy_id": strategy_id
                })
                logger.info(f"Generated hybrid strategy {strategy_id} from {strat1['name']} and {strat2['name']}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse error from Combiner Claude: {e}")
                
        except Exception as e:
            logger.error(f"Combine strategies error: {e}")
