"""
Inject a known-good control strategy: RSI-14 only (legacy feature, fully populated).
If this strategy gets entry_count > 0, the pipeline works and the issue is
normalized feature availability. If it also gets 0, the bug is in coder/backtest.
"""

import asyncio
import json
import uuid
from datetime import datetime
from loguru import logger
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient

CONTROL_SPEC = {
    "strategy_name": "control_rsi14_mean_reversion",
    "hypothesis": "RSI-14 mean reversion: oversold entry, overbought exit",
    "entry_conditions": ["rsi_14 < 40"],
    "exit_conditions": ["rsi_14 > 60"],
    "stop_loss": "2% below entry",
    "take_profit": "2% above entry",
    "position_sizing": "10% of portfolio",
    "timeframe": "1m",
    "asset_class": "crypto",
    "expected_sharpe": 1.0,
    "expected_win_rate": 0.55,
    "risk_level": "medium",
    "tags": ["mean_reversion", "control"],
}

CONTROL_CODE = """\
import pandas as pd
import numpy as np


class ControlRSI14MeanReversion:
    \"\"\"Control strategy: RSI-14 only (uses no normalized features).\"\"\"

    def generate_signals(self, df):
        if df is None or df.empty:
            return pd.Series(dtype=int)

        signals = pd.Series(0, index=df.index)

        entry = (df['rsi_14'] < 40)

        exit_ = (df['rsi_14'] > 60)

        signals.loc[entry.fillna(False)] = 1
        signals.loc[exit_.fillna(False)] = -1

        overlap = entry & exit_
        signals.loc[overlap.fillna(False)] = 0

        return signals
"""


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    strategy_id = str(uuid.uuid4())

    async with db.engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO strategies (id, name, code, parameters, status, created_at, author_agent)
                VALUES (:id, :name, :code, :parameters, :status, :created_at, :author_agent)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": strategy_id,
                "name": CONTROL_SPEC["strategy_name"],
                "code": CONTROL_CODE,
                "parameters": json.dumps(CONTROL_SPEC),
                "status": "pending_backtest",
                "created_at": datetime.utcnow(),
                "author_agent": "control_injector",
            },
        )

    logger.info(f"Injected control strategy: {strategy_id}")
    logger.info(f"  Name:   {CONTROL_SPEC['strategy_name']}")
    logger.info(f"  Entry:  {CONTROL_SPEC['entry_conditions']}")
    logger.info(f"  Exit:   {CONTROL_SPEC['exit_conditions']}")
    logger.info(f"  Status: pending_backtest")
    logger.info("")
    logger.info("The BacktestRunner will pick it up in the next cycle.")
    logger.info("After backtest, run validator, then check entry_count.")


if __name__ == "__main__":
    asyncio.run(main())
