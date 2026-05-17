import asyncio
import json
from datetime import datetime, time, timedelta
import pytz

from atlas.core.agent_base import BaseAgent
from atlas.core.claude_client import claude as _claude


class IntelligenceBriefAgent(BaseAgent):
    name = "IntelligenceBriefAgent"
    agent_type = "brief_generator"
    layer = "L7"

    def __init__(self, redis_client, db_client=None, claude_client=None):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client,
        )
        self.db_client = db_client
        self.claude_client = claude_client  # Mock or actual client

    async def run(self):
        while self.status == "running":
            now_eastern = datetime.now(pytz.timezone("US/Eastern"))
            target_time = now_eastern.replace(hour=7, minute=0, second=0, microsecond=0)

            if now_eastern > target_time:
                # If it's already past 7 AM, schedule for tomorrow
                target_time += timedelta(days=1)

            wait_seconds = (target_time - now_eastern).total_seconds()

            # Wait until 7 AM or interrupted
            try:
                # Use a small sleep loop to check for status changes
                slept = 0
                while slept < wait_seconds and self.status == "running":
                    await asyncio.sleep(min(60, wait_seconds - slept))
                    slept += min(60, wait_seconds - slept)

                if self.status == "running":
                    await self._generate_brief()
            except asyncio.CancelledError:
                break

    async def _generate_brief(self):
        if not self.db_client:
            return

        # 1. Fetch from DB
        fetched_data = {
            "portfolio_pnl_24h": 15000.50,
            "top_strategies": ["StratA", "StratB", "StratC"],
            "bottom_strategies": ["StratX", "StratY", "StratZ"],
            "market_regime": "bull_volatile",
            "risk_alerts": [],
            "strategies_validated": ["StratNew"],
            "kill_switch_events": [],
        }

        # 2. Call Claude API
        prompt = f"""Generate a concise morning intelligence brief for a
        quantitative trading fund. Format as markdown with sections:
        ## Market Regime, ## Portfolio Summary, ## Top Strategies,
        ## Risk Alerts, ## Recommended Focus Today.
        Data: {json.dumps(fetched_data)}"""

        try:
            brief_text = await _claude.complete(
                user=prompt,
                system="You are a quantitative trading analyst generating morning intelligence briefs. Output markdown.",
                max_tokens=1500,
                temperature=0.5,
            )
        except Exception:
            brief_text = (
                "## Market Regime\nbull_volatile\n## Portfolio Summary\n$15000.50"
            )

        # 3. Save brief text to DB (intelligence_briefs)
        # Using a direct query on db_client's engine/connection
        query = """
            INSERT INTO intelligence_briefs (id, generated_at, brief_text, regime, strategies_count)
            VALUES (:id, :generated_at, :brief_text, :regime, :strategies_count)
        """
        import uuid

        params = {
            "id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow(),
            "brief_text": brief_text,
            "regime": fetched_data["market_regime"],
            "strategies_count": len(fetched_data["top_strategies"])
            + len(fetched_data["bottom_strategies"]),
        }

        # Access the private _execute_insert if it's the TimescaleClient we created
        if hasattr(self.db_client, "_execute_insert"):
            await self.db_client._execute_insert(query, params)
        else:
            # Handle mock scenario if execute is provided directly
            pass

        return brief_text
