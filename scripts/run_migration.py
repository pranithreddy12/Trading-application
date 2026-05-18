"""Apply schema.sql changes to live PostgreSQL that weren't auto-applied (docker init scripts only run on first container boot)."""

import asyncio
import asyncpg
from atlas.config.settings import get_settings

MIGRATION_SQL = """
-- 7. backtest_trades
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    strategy_id UUID NOT NULL,
    symbol TEXT NOT NULL,
    entry_time TIMESTAMPTZ,
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC,
    exit_price NUMERIC,
    side TEXT,
    pnl NUMERIC,
    pnl_pct NUMERIC,
    bars_held INT,
    exit_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy ON backtest_trades (strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_entry ON backtest_trades (entry_time);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades (symbol);

-- market_data_l1 new columns
ALTER TABLE market_data_l1 ADD COLUMN IF NOT EXISTS asset_class TEXT NOT NULL DEFAULT 'crypto';
ALTER TABLE market_data_l1 ADD COLUMN IF NOT EXISTS ingestion_time TIMESTAMPTZ DEFAULT NOW();

-- strategies new columns
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS raw_response TEXT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS normalized_strategy JSONB;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS compile_error TEXT;

-- features_wide materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS features_wide AS
SELECT
    time,
    symbol,
    MAX(CASE WHEN feature_name='returns' THEN value END) AS returns,
    MAX(CASE WHEN feature_name='rsi_14' THEN value END) AS rsi_14,
    MAX(CASE WHEN feature_name='ema_12' THEN value END) AS ema_12,
    MAX(CASE WHEN feature_name='ema_26' THEN value END) AS ema_26,
    MAX(CASE WHEN feature_name='macd' THEN value END) AS macd,
    MAX(CASE WHEN feature_name='macd_signal' THEN value END) AS macd_signal,
    MAX(CASE WHEN feature_name='bollinger_upper' THEN value END) AS bollinger_upper,
    MAX(CASE WHEN feature_name='bollinger_lower' THEN value END) AS bollinger_lower,
    MAX(CASE WHEN feature_name='rolling_volatility' THEN value END) AS rolling_volatility,
    MAX(CASE WHEN feature_name='vwap' THEN value END) AS vwap
FROM features
GROUP BY time, symbol;
CREATE UNIQUE INDEX IF NOT EXISTS idx_features_wide_time_symbol ON features_wide (time, symbol);
"""


async def run_migration():
    s = get_settings()
    raw_url = s.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(raw_url)

    for stmt in MIGRATION_SQL.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                await conn.execute(stmt)
                print(f"OK: {stmt[:80]}...")
            except Exception as e:
                print(f"SKIP ({e}): {stmt[:80]}...")

    # Verify
    tables = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    )
    print("\n=== TABLES ===")
    for r in tables:
        print(f"  {r['table_name']}")

    count = await conn.fetchval("SELECT COUNT(*) FROM backtest_trades")
    print(f"\nbacktest_trades rows: {count}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
