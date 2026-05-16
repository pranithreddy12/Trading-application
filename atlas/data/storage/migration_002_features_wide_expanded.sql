/*
 * migration_002_features_wide_expanded.sql
 *
 * Expands features_wide materialized view to include all normalized features
 * used by L2 Ideator/Coder strategies.
 *
 * Adds columns previously missing:
 *   log_returns, sma_5, sma_20, ema_5,
 *   price_vs_vwap_pct, ema_spread_pct, relative_volume,
 *   bollinger_band_position, volatility_regime, trend_strength
 *
 * ⚠ This drops and recreates the materialized view, requiring a full refresh.
 *    For large datasets, this may take significant time and I/O.
 *
 * ⚠ BACKUP FIRST:
 *    pg_dump -h localhost -p 5433 -U postgres -d atlas \
 *      --table=features_wide \
 *      > atlas_features_wide_backup_$(date +%Y%m%d).sql
 *
 * ⚠ Rollback:
 *    psql -h localhost -p 5433 -U postgres -d atlas < backup_file.sql
 */

BEGIN;

-- ============================================================
-- 1. Drop old materialized view (CASCADE to drop dependent indexes)
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS features_wide CASCADE;

-- ============================================================
-- 2. Recreate with ALL required columns
-- ============================================================
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
GROUP BY time, symbol;

-- ============================================================
-- 3. Recreate unique index for CONCURRENT REFRESH support
-- ============================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_features_wide_time_symbol
    ON features_wide (time, symbol);

-- ============================================================
-- 4. Refresh to populate initial data
-- ============================================================
REFRESH MATERIALIZED VIEW features_wide;

COMMIT;
