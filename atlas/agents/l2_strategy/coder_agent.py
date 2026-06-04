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
from atlas.core.code_sanitizer import sanitize_python_code
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

            # Extract economic parameters from normalized strategy
            if isinstance(params, dict):
                valid_regimes = params.get("valid_regimes", [])
                hold_min = params.get("hold_time_min", 3)
                hold_max = params.get("hold_time_max", 40)
                cooldown_bars = params.get("cooldown_bars", 5)
            else:
                valid_regimes = []
                hold_min = 3
                hold_max = 40
                cooldown_bars = 5

            # =====================================================
            # GENERATE CODE
            # =====================================================
            code = self._generate_code(
                strategy_name, entry, exit_, valid_regimes,
                hold_min=hold_min, hold_max=hold_max, cooldown_bars=cooldown_bars,
            )

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
            code = sanitize_python_code(code).code
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
        valid_regimes: list | None = None,
        hold_min: int = 3,
        hold_max: int = 40,
        cooldown_bars: int = 5,
    ) -> str:
        class_name = self._sanitize_class_name(strategy_name)
        condition_block = conditions_to_code(entry, exit_)

        # Generate regime classification code block
        regime_block = self._generate_regime_classification_code(valid_regimes)

        # Build code with no leading indentation on the template.
        # The regime computation block is already 8-space indented in the string
        # literal. We normalise it with dedent then re-indent to 8 spaces so it
        # always lands correctly inside generate_signals() regardless of where
        # this method is called from.
        regime_code_normalised = textwrap.indent(
            textwrap.dedent(self._regime_computation_code).strip("\n"),
            "        ",  # 8 spaces — inside generate_signals()
        )
        generated_code = textwrap.dedent(f"""\
import pandas as pd
import numpy as np


class {class_name}:
    \"\"\"Auto-generated from normalized strategy spec.\"\"\"
{regime_block}

    def generate_signals(self, df):
        if df is None or df.empty:
            return pd.Series(dtype=int)

        signals = pd.Series(0, index=df.index)

{condition_block}

        # Regime classification — determines which market states are tradeable
{regime_code_normalised}

        # Position state machine — prevents exit spam, enforces holding discipline
        in_position = False
        bars_held = 0
        cooldown = 0
        MIN_HOLD_BARS = {hold_min}
        MAX_HOLD_BARS = {hold_max}
        entry_clean = entry.fillna(False)
        exit_clean = exit_.fillna(False)

        for i in range(len(df)):
            if cooldown > 0:
                cooldown -= 1
                continue

            if not in_position:
                if entry_clean.iloc[i]:
                    # Regime gate — skip entry if current regime not in valid set
                    # Allow 'unknown' (NaN/degraded features) to pass through;
                    # the entry conditions themselves will naturally filter NaN.
                    if self.VALID_REGIMES and df['_regime'].iloc[i] not in self.VALID_REGIMES and df['_regime'].iloc[i] != 'unknown':
                        continue
                    signals.iloc[i] = 1
                    in_position = True
                    bars_held = 1
            else:
                bars_held += 1
                if bars_held >= MAX_HOLD_BARS or (bars_held >= MIN_HOLD_BARS and exit_clean.iloc[i]):
                    signals.iloc[i] = -1
                    in_position = False
                    bars_held = 0
                    cooldown = {cooldown_bars}

        return signals
""")
        return generated_code

    # Registry of regime classification code that runs inside generate_signals()
    _regime_computation_code = """\
        df['_regime'] = 'unknown'
        df.loc[df['volatility_regime'] > 1.4, '_vol_regime'] = 'high_vol'
        df.loc[df['volatility_regime'] < 0.7, '_vol_regime'] = 'low_vol'
        df.loc[(df['volatility_regime'] >= 0.7) & (df['volatility_regime'] <= 1.4), '_vol_regime'] = 'normal_vol'
        df.loc[df['trend_strength'] > 0.002, '_trend_regime'] = 'trending'
        df.loc[df['trend_strength'] <= 0.002, '_trend_regime'] = 'ranging'
        df.loc[df['ema_spread_pct'] > 0.001, '_direction'] = 'bullish'
        df.loc[df['ema_spread_pct'] < -0.001, '_direction'] = 'bearish'
        df.loc[(df['ema_spread_pct'] >= -0.001) & (df['ema_spread_pct'] <= 0.001), '_direction'] = 'neutral'
        df.loc[df['bollinger_band_position'] > 0.8, '_bb_regime'] = 'overbought'
        df.loc[df['bollinger_band_position'] < 0.2, '_bb_regime'] = 'oversold'
        df.loc[(df['bollinger_band_position'] >= 0.2) & (df['bollinger_band_position'] <= 0.8), '_bb_regime'] = 'normal'
        # Composite regime — combine volatility + trend for meaningful classification
        df.loc[df['_vol_regime'] == 'high_vol', '_regime'] = 'high_vol'
        df.loc[df['_vol_regime'] == 'low_vol', '_regime'] = 'low_vol'
        df.loc[(df['_direction'] == 'bullish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bullish'
        df.loc[(df['_direction'] == 'bearish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bearish'
        df.loc[(df['_trend_regime'] == 'ranging') & (df['_vol_regime'] == 'normal_vol'), '_regime'] = 'ranging'
        df.loc[df['_bb_regime'] == 'overbought', '_regime'] = 'overbought'
        df.loc[df['_bb_regime'] == 'oversold', '_regime'] = 'oversold'
"""

    def _generate_regime_classification_code(self, valid_regimes: list | None = None) -> str:
        """
        Generate the VALID_REGIMES class constant based on strategy spec.
        If no valid_regimes specified, defaults to all regimes (no restriction).
        """
        if not valid_regimes:
            # Default: all regimes allowed — no restriction
            return f"""
    # Market regimes this strategy is designed for (empty = all allowed)
    VALID_REGIMES: list = []
"""
        regimes_str = ", ".join(repr(r) for r in valid_regimes)
        return f"""
    # Market regimes this strategy is designed for
    VALID_REGIMES: list = [{regimes_str}]
"""


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
