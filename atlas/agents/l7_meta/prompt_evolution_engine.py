"""
prompt_evolution_engine.py — L7 Meta Agent for prompt evolution and optimization.

Capabilities:
- Prompt mutation
- Prompt scoring
- Prompt survivability tracking
- Strategy-generation effectiveness ranking
- Regime-conditioned prompt optimization
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy.sql import text

from atlas.core.agent_base import BaseAgent


class PromptEvolutionEngine(BaseAgent):
    """
    L7 Meta Agent — Evolves and optimizes prompts for strategy generation.
    """

    name = "PromptEvolutionEngine"
    agent_type = "prompt_evolution"
    layer = "L7"

    def __init__(self, redis_client, db_client):
        super().__init__(self.name, self.agent_type, self.layer, redis_client)
        self.db = db_client
        self._run_interval = 7200  # Every 2 hours

    async def run(self):
        logger.info(f"{self.name}: Starting prompt evolution engine")

        while self.status == "running":
            try:
                await self._evolve_prompts()
            except Exception as e:
                logger.error(f"{self.name}: Prompt evolution error: {e}")

            for _ in range(self._run_interval // 10):
                await self._sleep(10)
                if self.status != "running":
                    return

    async def _sleep(self, seconds: int):
        import asyncio
        await asyncio.sleep(seconds)

    async def _evolve_prompts(self):
        """Run prompt evolution cycle."""
        # Get current prompt performance
        current_prompts = await self._load_prompt_performance()
        if not current_prompts:
            logger.info(f"{self.name}: No prompts to evolve")
            return

        # Score and rank prompts
        ranked = sorted(
            current_prompts,
            key=lambda p: p.get("effectiveness_score", 0),
            reverse=True,
        )

        # Retire bottom performers
        if len(ranked) > 5:
            for prompt in ranked[5:]:
                if prompt.get("effectiveness_score", 0) < 0.3:
                    await self._retire_prompt(prompt["id"])

        # Generate new prompt variants
        if ranked:
            best = ranked[0]
            new_variant = await self._mutate_prompt(best)
            if new_variant:
                await self._register_prompt(new_variant, parent_id=best["id"])

        logger.info(
            f"{self.name}: Evolution cycle — "
            f"{len(current_prompts)} prompts, best_score={ranked[0].get('effectiveness_score', 0):.2f}" if ranked else "no prompts"
        )

    async def _load_prompt_performance(self) -> list[dict]:
        """Load prompt templates with effectiveness scores."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT p.id, p.prompt_type, p.prompt_text,
                           p.archetype, p.generation_count,
                           p.success_count, p.effectiveness_score,
                           p.created_at
                    FROM prompt_templates p
                    WHERE p.status = 'active'
                    ORDER BY p.effectiveness_score DESC
                """)
            )
            return [
                {
                    "id": str(row[0]),
                    "prompt_type": str(row[1]),
                    "prompt_text": str(row[2]),
                    "archetype": str(row[3]) if row[3] else "",
                    "generation_count": int(row[4] or 0),
                    "success_count": int(row[5] or 0),
                    "effectiveness_score": float(row[6] or 0),
                    "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                }
                for row in r.fetchall()
            ]

    async def _mutate_prompt(self, parent: dict) -> Optional[str]:
        """Create a mutated variant of a prompt."""
        import random

        mutation_type = random.choice(
            ["tighten", "loosen", "add_constraint", "remove_constraint", "rephrase"]
        )

        text = parent["prompt_text"]
        mutations = {
            "tighten": text + "\n- Be more selective: require higher conviction signals.",
            "loosen": text + "\n- Be more permissive: allow moderate conviction signals.",
            "add_constraint": text + "\n- Prefer strategies with asymmetric reward:risk profiles.",
            "remove_constraint": None,
            "rephrase": text,
        }

        mutated = mutations.get(mutation_type, text)
        if mutated is None:
            return None

        return mutated

    async def _register_prompt(
        self,
        prompt_text: str,
        prompt_type: str = "ideator",
        archetype: str = "",
        parent_id: Optional[str] = None,
    ):
        """Register a new prompt variant."""
        prompt_id = self.select_trace_id()
        await self.db._execute_insert(
            """
            INSERT INTO prompt_templates
                (id, prompt_type, prompt_text, archetype,
                 status, parent_prompt_id, created_at)
            VALUES
                (:id, :type, :text, :archetype,
                 'active', :parent_id, NOW())
            """,
            {
                "id": prompt_id,
                "type": prompt_type,
                "text": prompt_text,
                "archetype": archetype,
                "parent_id": parent_id,
            },
        )
        return prompt_id

    async def _retire_prompt(self, prompt_id: str):
        """Retire an underperforming prompt."""
        await self.db._execute_insert(
            """
            UPDATE prompt_templates
            SET status = 'retired', updated_at = NOW()
            WHERE id = :id
            """,
            {"id": prompt_id},
        )

    async def record_generation_result(
        self,
        prompt_id: str,
        strategy_id: str,
        success: bool,
        score: Optional[float] = None,
    ):
        """Record the result of a strategy generation from a prompt."""
        await self.db._execute_insert(
            """
            INSERT INTO prompt_generation_log
                (id, prompt_id, strategy_id, success,
                 generation_score, generated_at)
            VALUES
                (:id, :prompt_id, :strategy_id, :success,
                 :score, NOW())
            """,
            {
                "id": self.select_trace_id(),
                "prompt_id": prompt_id,
                "strategy_id": strategy_id,
                "success": success,
                "score": score,
            },
        )
