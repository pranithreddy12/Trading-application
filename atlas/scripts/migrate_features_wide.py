"""
One-shot migration: drop+recreate features_wide with all normalized feature columns,
then verify data exists in the features table.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from atlas.config.settings import get_settings

EXPECTED_COLUMNS = [
    "returns",
    "log_returns",
    "rsi_14",
    "macd",
    "macd_signal",
    "vwap",
    "sma_5",
    "sma_20",
    "ema_5",
    "ema_12",
    "ema_26",
    "bollinger_lower",
    "bollinger_upper",
    "rolling_volatility",
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
]

MV_SQL = """
CREATE MATERIALIZED VIEW features_wide AS
SELECT
    time,
    symbol,
    MAX(CASE WHEN feature_name='returns'               THEN value END) AS returns,
    MAX(CASE WHEN feature_name='log_returns'           THEN value END) AS log_returns,
    MAX(CASE WHEN feature_name='rsi_14'                THEN value END) AS rsi_14,
    MAX(CASE WHEN feature_name='macd'                  THEN value END) AS macd,
    MAX(CASE WHEN feature_name='macd_signal'           THEN value END) AS macd_signal,
    MAX(CASE WHEN feature_name='vwap'                  THEN value END) AS vwap,
    MAX(CASE WHEN feature_name='sma_5'                 THEN value END) AS sma_5,
    MAX(CASE WHEN feature_name='sma_20'                THEN value END) AS sma_20,
    MAX(CASE WHEN feature_name='ema_5'                 THEN value END) AS ema_5,
    MAX(CASE WHEN feature_name='ema_12'                THEN value END) AS ema_12,
    MAX(CASE WHEN feature_name='ema_26'                THEN value END) AS ema_26,
    MAX(CASE WHEN feature_name='bollinger_lower'       THEN value END) AS bollinger_lower,
    MAX(CASE WHEN feature_name='bollinger_upper'       THEN value END) AS bollinger_upper,
    MAX(CASE WHEN feature_name='rolling_volatility'    THEN value END) AS rolling_volatility,
    MAX(CASE WHEN feature_name='price_vs_vwap_pct'     THEN value END) AS price_vs_vwap_pct,
    MAX(CASE WHEN feature_name='ema_spread_pct'        THEN value END) AS ema_spread_pct,
    MAX(CASE WHEN feature_name='relative_volume'       THEN value END) AS relative_volume,
    MAX(CASE WHEN feature_name='bollinger_band_position' THEN value END) AS bollinger_band_position,
    MAX(CASE WHEN feature_name='volatility_regime'     THEN value END) AS volatility_regime,
    MAX(CASE WHEN feature_name='trend_strength'        THEN value END) AS trend_strength
FROM features
GROUP BY time, symbol
"""


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=True)

    async with engine.begin() as conn:
        # Step 1: Check current columns
        print("\n=== CURRENT features_wide COLUMNS ===")
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'features_wide' ORDER BY ordinal_position"
            )
        )
        current_cols = [row[0] for row in result.fetchall()]
        print(f"Current columns ({len(current_cols)}): {current_cols}")

        # Step 2: Drop old MV
        print("\n=== DROPPING OLD features_wide ===")
        await conn.execute(
            text("DROP MATERIALIZED VIEW IF EXISTS features_wide CASCADE")
        )
        print("Dropped.")

        # Step 3: Create new MV
        print("\n=== CREATING NEW features_wide ===")
        await conn.execute(text(MV_SQL))
        print("Created.")

        # Step 4: Create unique index
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_features_wide_time_symbol ON features_wide (time, symbol)"
            )
        )
        print("Index created.")

        # Step 5: Refresh
        print("\n=== REFRESHING MATERIALIZED VIEW ===")
        await conn.execute(text("REFRESH MATERIALIZED VIEW features_wide"))
        print("Refreshed.")

    # Step 6: Verify new columns
    async with engine.connect() as conn:
        print("\n=== VERIFY: NEW features_wide COLUMNS ===")
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'features_wide' ORDER BY ordinal_position"
            )
        )
        new_cols = [row[0] for row in result.fetchall()]
        print(f"New columns ({len(new_cols)}): {new_cols}")

        missing = [c for c in EXPECTED_COLUMNS if c not in new_cols]
        if missing:
            print(f"ERROR — still missing: {missing}")
        else:
            print("ALL 20 EXPECTED COLUMNS PRESENT ✓")

        # Step 7: Check if normalized features exist in raw features table
        print("\n=== CHECK: Do normalized features exist in raw `features` table? ===")
        norm_features = [
            "price_vs_vwap_pct",
            "ema_spread_pct",
            "relative_volume",
            "bollinger_band_position",
            "volatility_regime",
            "trend_strength",
        ]
        for feat in norm_features:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM features WHERE feature_name = :f"),
                {"f": feat},
            )
            count = result.scalar()
            print(f"  {feat}: {count} rows")

        # Step 8: Sample features_wide data
        print("\n=== SAMPLE: features_wide rows with normalized features ===")
        result = await conn.execute(
            text("""
                SELECT time, symbol,
                       price_vs_vwap_pct, ema_spread_pct, relative_volume,
                       bollinger_band_position, volatility_regime, trend_strength
                FROM features_wide
                WHERE price_vs_vwap_pct IS NOT NULL
                LIMIT 5
            """)
        )
        rows = result.fetchall()
        for row in rows:
            print(
                f"  {row.time} {row.symbol}: pvv={row.price_vs_vwap_pct:.6f}, es={row.ema_spread_pct:.6f}, rv={row.relative_volume:.4f}, bbp={row.bollinger_band_position:.4f}, vr={row.volatility_regime:.4f}, ts={row.trend_strength:.6f}"
            )

        # Step 9: Check NVDA specifically
        print("\n=== NVDA: features_wide row count + normalized feature presence ===")
        result = await conn.execute(
            text("SELECT COUNT(*) FROM features_wide WHERE symbol = 'NVDA'")
        )
        print(f"  NVDA rows in features_wide: {result.scalar()}")

        result = await conn.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE price_vs_vwap_pct IS NOT NULL) AS has_pvv,
                    COUNT(*) FILTER (WHERE ema_spread_pct IS NOT NULL) AS has_es,
                    COUNT(*) FILTER (WHERE relative_volume IS NOT NULL) AS has_rv,
                    COUNT(*) FILTER (WHERE bollinger_band_position IS NOT NULL) AS has_bbp,
                    COUNT(*) FILTER (WHERE volatility_regime IS NOT NULL) AS has_vr,
                    COUNT(*) FILTER (WHERE trend_strength IS NOT NULL) AS has_ts
                FROM features_wide
                WHERE symbol = 'NVDA'
            """)
        )
        row = result.fetchone()
        print(
            f"  NVDA non-null counts: pvv={row[0]}, es={row[1]}, rv={row[2]}, bbp={row[3]}, vr={row[4]}, ts={row[5]}"
        )

    await engine.dispose()
    print("\n=== MIGRATION COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
