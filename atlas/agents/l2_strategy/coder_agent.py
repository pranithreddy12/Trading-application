import textwrap

import asyncio
import json
import re
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.strategy_normalizer import (
    normalize_strategy,
    conditions_to_code,
)
from atlas.core.event_lineage import EventLineageClient


class CoderAgent(BaseAgent):
    """
    Converts strategy specifications into executable Python code.
    Uses normalized strategy conditions to generate signal logic.
    STRICT MODE:
    - compile() validation before DB save
    - invalid code => code_failed
    """

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name="CoderAgent",
            agent_type="coder",
            layer="L2",
            redis_client=redis_client,
        )
        self.db_client = db_client

    async def run(self):
        logger.info("CoderAgent run loop started")

        while True:
            try:
                strategies = await self.db_client.get_strategies_by_status(
                    "pending_code"
                )

                logger.info(f"Found {len(strategies)} pending strategies")

                for strategy in strategies:
                    await self._code_strategy(strategy)

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(
                    f"CoderAgent run loop error: {type(e).__name__}: {e}",
                    exc_info=True,
                )

                await asyncio.sleep(5)

    async def _code_strategy(self, strategy_record: dict):
        strategy_id = strategy_record["id"]
        trace_id = strategy_record.get("trace_id")

        try:
            strategy_name = strategy_record["name"]
            params = strategy_record["parameters"]

            if isinstance(params, str):
                params = json.loads(params)

            # =====================================================
            # NORMALIZE STRATEGY
            # =====================================================
            params = normalize_strategy(params)

            entry = params.get("entry_conditions", [])
            exit_ = params.get("exit_conditions", [])

            if not entry:
                raise ValueError("No valid entry conditions after normalization")

            # =====================================================
            # GENERATE CODE
            # =====================================================
            code = self._generate_code(strategy_name, entry, exit_)

            # =====================================================
            # STRICT COMPILE VALIDATION
            # =====================================================
            try:
                compile(code, f"<strategy_{strategy_name}>", "exec")

            except Exception as compile_err:
                logger.error(
                    f"COMPILE FAILED for {strategy_id} "
                    f"({strategy_name}): "
                    f"{type(compile_err).__name__}: {compile_err}"
                )

                logger.error(f"FAILED GENERATED CODE:\n{code}")

                await self.db_client.update_strategy_status(
                    strategy_id,
                    "code_failed",
                )

                try:
                    await self.db_client.update_strategy_fields(
                        strategy_id,
                        compile_error=f"{type(compile_err).__name__}: {compile_err}",
                    )
                except Exception as field_err:
                    logger.warning(f"Compile error field update failed: {field_err}")

                await self._log_lifecycle(
                    trace_id,
                    strategy_id,
                    "coder",
                    "failed",
                    {
                        "error": f"{type(compile_err).__name__}: {str(compile_err)[:200]}"
                    },
                )

                try:
                    await self.db_client.log(
                        agent_id="CoderAgent",
                        level="ERROR",
                        message=f"Compile failed for {strategy_id}: {type(compile_err).__name__}: {compile_err}",
                        metadata={
                            "strategy_id": str(strategy_id),
                            "strategy_name": strategy_name,
                            "error_type": type(compile_err).__name__,
                            "error": str(compile_err),
                            "code": code,
                        },
                    )
                except Exception as log_err:
                    logger.warning(f"System log write failed: {log_err}")

                return

            # =====================================================
            # SAVE ONLY VALID CODE
            # =====================================================
            await self.db_client.update_strategy_code(
                strategy_id,
                code,
                "pending_backtest",
            )

            await self._log_lifecycle(
                trace_id,
                strategy_id,
                "coder",
                "completed",
                {"code_len": len(code), "strategy_name": strategy_name},
            )

            logger.info(f"Successfully coded strategy {strategy_id} ({strategy_name})")

        except Exception as e:
            logger.error(
                f"Code strategy error for {strategy_id}: {type(e).__name__}: {e}",
                exc_info=True,
            )

            try:
                await self.db_client.update_strategy_status(
                    strategy_id,
                    "code_failed",
                )
            except Exception:
                pass

            await self._log_lifecycle(
                trace_id,
                strategy_id,
                "coder",
                "failed",
                {"error": f"{type(e).__name__}: {str(e)[:200]}"},
            )

    async def _log_lifecycle(self, trace_id, strategy_id, stage, status, metadata=None):
        if not trace_id:
            return
        try:
            lineage = EventLineageClient(self.db_client)
            await lineage.create_event(
                trace_id=trace_id,
                stage=stage,
                status=status,
                actor=self.name,
                strategy_id=strategy_id,
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning(f"Lifecycle event log failed ({stage}/{status}): {exc}")

    def _sanitize_class_name(self, strategy_name: str) -> str:
        """
        Python-safe class name.
        """
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", strategy_name)

        if sanitized and sanitized[0].isdigit():
            sanitized = f"Strategy_{sanitized}"

        return sanitized

    def _indent_condition_block(self, condition_block: str) -> str:
        """
        Ensures multiline generated condition code is properly
        indented inside generate_signals().
        """
        return "\n        ".join(condition_block.splitlines())

    # =====================================================
    def _generate_code(
        self,
        strategy_name: str,
        entry: list,
        exit_: list,
    ) -> str:
        class_name = self._sanitize_class_name(strategy_name)
        condition_block = conditions_to_code(entry, exit_)

        # Build code with no leading indentation on the template
        # textwrap.dedent removes any accidental indentation from
        # the f-string being inside an indented method
        generated_code = textwrap.dedent(f"""\
import pandas as pd
import numpy as np


class {class_name}:
    \"\"\"Auto-generated from normalized strategy spec.\"\"\"

    def generate_signals(self, df):
        if df is None or df.empty:
            return pd.Series(dtype=int)

        signals = pd.Series(0, index=df.index)

{condition_block}

        # Edge-trigger entries — fire only on transition False→True
        buy = entry.fillna(False) & ~entry.fillna(False).shift(1).fillna(False)

        # Edge-trigger exits — fire only on transition False→True
        sell = exit_.fillna(False) & ~exit_.fillna(False).shift(1).fillna(False)

        # Apply entries
        signals.loc[buy] = 1

        # Apply exits
        signals.loc[sell] = -1

        # Neutralize overlaps
        overlap = buy & sell
        signals.loc[overlap.fillna(False)] = 0

        return signals
""")
        return generated_code


async def main():
    logger.info("Starting CoderAgent...")
    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()

    redis_client = Redis.from_url(settings.redis_url)

    agent = CoderAgent(redis_client, db_client)
    await agent.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
