"""
Backfill ONLY missing normalized features for symbols that have legacy features
but lack normalized ones (price_vs_vwap_pct, ema_spread_pct, relative_volume,
bollinger_band_position, volatility_regime, trend_strength).
"""

import asyncio
from loguru import logger
import pandas as pd
import numpy as np
from sqlalchemy import text
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l1_data.feature_agent import FeatureAgent

NORMALIZED_FEATURES = [
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
]


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    fa = FeatureAgent()
    await fa.connect()

    # Find symbols that have legacy features but MISSING normalized features
    async with db.engine.connect() as conn:
        rows = await conn.execute(
            text("""
                SELECT DISTINCT f.symbol
                FROM features f
                WHERE f.feature_name = 'returns'
                  AND NOT EXISTS (
                    SELECT 1 FROM features f2
                    WHERE f2.symbol = f.symbol
                      AND f2.feature_name = 'price_vs_vwap_pct'
                  )
                ORDER BY f.symbol
            """)
        )
        symbols = [r[0] for r in rows.fetchall()]

    if not symbols:
        logger.info("No symbols need normalized feature backfill")
        return

    logger.info(f"Symbols needing normalized feature backfill: {symbols}")

    total_inserted = 0
    for symbol in symbols:
        logger.info(f"Processing {symbol}...")
        df = await fa.fetch_recent_bars(symbol, limit=100000)
        if df.empty:
            logger.warning(f"No bars for {symbol}")
            continue

        feat_df = fa.compute_features(df)
        if feat_df.empty:
            logger.warning(f"No features computed for {symbol}")
            continue

        records = []
        for _, row in feat_df.iterrows():
            ts = row["timestamp"]
            for col in NORMALIZED_FEATURES:
                val = row.get(col)
                if val is None or pd.isna(val) or np.isinf(val):
                    continue
                records.append(
                    {
                        "t": ts,
                        "s": symbol,
                        "n": col,
                        "v": float(val),
                    }
                )

        if not records:
            logger.warning(f"No normalized feature values computed for {symbol}")
            continue

        inserted = 0
        BATCH = 1000
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            async with db.engine.begin() as conn:
                for rec in batch:
                    await conn.execute(
                        text(
                            """INSERT INTO features (time, symbol, feature_name, value)
                               VALUES (:t, :s, :n, :v) ON CONFLICT DO NOTHING"""
                        ),
                        rec,
                    )
            inserted += len(batch)
            logger.info(f"  {symbol}: {inserted}/{len(records)}")

        total_inserted += inserted
        logger.info(f"{symbol}: {inserted} normalized feature rows inserted")

    # Refresh the materialized view
    async with db.engine.begin() as conn:
        await conn.execute(text("REFRESH MATERIALIZED VIEW features_wide"))
    logger.info(f"Done. Total normalized feature rows inserted: {total_inserted}")

    # Verify
    async with db.engine.connect() as conn:
        for feat in NORMALIZED_FEATURES:
            r = await conn.execute(
                text("SELECT COUNT(*) FROM features WHERE feature_name = :f"),
                {"f": feat},
            )
            logger.info(f"  {feat}: {r.scalar()} total rows")

    await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
