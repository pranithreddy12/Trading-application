"""
Backfill features table for ALL symbols — including normalized features
for symbols that were backfilled before normalized features existed.
Uses ON CONFLICT DO NOTHING so re-runs are safe.
"""

import asyncio
from loguru import logger
import pandas as pd
import numpy as np
from sqlalchemy import text
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l1_data.feature_agent import FeatureAgent


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    fa = FeatureAgent()
    await fa.connect()

    # Find symbols with INSUFFICIENT normalized features (< 10 rows = not properly backfilled)
    async with db.engine.connect() as conn:
        rows = await conn.execute(
            text("""
                SELECT DISTINCT m.symbol
                FROM market_data_l1 m
                WHERE (
                    SELECT COUNT(*)
                    FROM features f
                    WHERE f.symbol = m.symbol
                      AND f.feature_name = 'price_vs_vwap_pct'
                ) < 10
                ORDER BY m.symbol
            """)
        )
        symbols = [r[0] for r in rows.fetchall()]

    if not symbols:
        logger.info("All symbols have sufficient normalized features")
        return

    logger.info(f"Symbols needing backfill (missing normalized features): {symbols}")

    total = 0
    for symbol in symbols:
        df = await fa.fetch_recent_bars(symbol, limit=100000)
        if df.empty:
            continue
        feat_df = fa.compute_features(df)
        if feat_df.empty:
            continue

        feature_cols = [
            c
            for c in feat_df.columns
            if c
            not in (
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            )
        ]

        records = []
        for _, row in feat_df.iterrows():
            ts = row["timestamp"]
            for col in feature_cols:
                val = row[col]
                if pd.isna(val) or np.isinf(val):
                    continue
                records.append({"t": ts, "s": symbol, "n": col, "v": float(val)})

        inserted = 0
        BATCH = 1000
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            async with db.engine.begin() as conn:
                for rec in batch:
                    await conn.execute(
                        text("""INSERT INTO features (time, symbol, feature_name, value)
                                VALUES (:t, :s, :n, :v) ON CONFLICT DO NOTHING"""),
                        rec,
                    )
            inserted += len(batch)
            logger.info(f"  {symbol}: {inserted}/{len(records)}")

        total += inserted
        logger.info(f"{symbol}: {inserted} feature rows done")

    async with db.engine.begin() as conn:
        await conn.execute(text("REFRESH MATERIALIZED VIEW features_wide"))
    logger.info(f"Total feature rows inserted: {total}")


if __name__ == "__main__":
    asyncio.run(main())
