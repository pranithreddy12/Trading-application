"""
Insert EMA crossover seed strategy into DB.
Run: python atlas/scripts/insert_seed.py
"""
import asyncio
import json
import uuid
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

CODE = (
    "import pandas as pd\n"
    "import numpy as np\n"
    "\n"
    "class Strategy_EMA_Crossover_Seed:\n"
    "    def generate_signals(self, df):\n"
    "        signals = pd.Series(0, index=df.index)\n"
    "        if len(df) < 30:\n"
    "            return signals\n"
    "        fast = df['close'].ewm(span=9, adjust=False).mean()\n"
    "        slow = df['close'].ewm(span=21, adjust=False).mean()\n"
    "        buy  = (fast > slow) & (fast.shift(1) <= slow.shift(1))\n"
    "        sell = (fast < slow) & (fast.shift(1) >= slow.shift(1))\n"
    "        signals[buy]  =  1\n"
    "        signals[sell] = -1\n"
    "        return signals\n"
    "    def get_parameters(self): return {}\n"
    "    def validate(self): return True\n"
)

PARAMS = json.dumps({
    "asset_class": "equity",
    "timeframe": "1m",
    "entry_conditions": ["ema_12 > ema_26"],
    "exit_conditions": ["ema_12 < ema_26"],
    "tags": ["seed", "equity"]
})


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    async with db.engine.begin() as conn:
        # Remove any existing seed
        await conn.execute(
            text("DELETE FROM strategies WHERE name = 'EMA_Crossover_Seed'")
        )
        # Insert fresh
        await conn.execute(
            text("""
                INSERT INTO strategies
                    (id, name, code, status, parameters, author_agent)
                VALUES
                    (:id, :name, :code, :status, CAST(:params AS jsonb), :author)
            """),
            {
                "id":     str(uuid.uuid4()),
                "name":   "EMA_Crossover_Seed",
                "code":   CODE,
                "status": "pending_backtest",
                "params": PARAMS,
                "author": "ManualSeed",
            }
        )

    print("Seed strategy inserted successfully")

    async with db.engine.connect() as conn:
        r = await conn.execute(
            text("SELECT name, status FROM strategies WHERE name = 'EMA_Crossover_Seed'")
        )
        row = r.fetchone()
        if row:
            print(f"Confirmed in DB: {row.name} -> {row.status}")
        else:
            print("ERROR: seed not found after insert")


if __name__ == "__main__":
    asyncio.run(main())