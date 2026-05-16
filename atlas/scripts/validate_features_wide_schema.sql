-- ============================================================
-- validate_features_wide_schema.sql
-- Run after migration_002 to verify features_wide has all columns
-- ============================================================

-- 1. Verify ALL expected columns exist
SELECT
    column_name,
    data_type,
    CASE
        WHEN column_name IN (
            'returns', 'log_returns', 'rsi_14', 'macd', 'macd_signal',
            'vwap', 'sma_5', 'sma_20', 'ema_5', 'ema_12', 'ema_26',
            'bollinger_lower', 'bollinger_upper', 'rolling_volatility',
            'price_vs_vwap_pct', 'ema_spread_pct', 'relative_volume',
            'bollinger_band_position', 'volatility_regime', 'trend_strength'
        ) THEN 'REQUIRED'
        ELSE 'metadata'
    END AS category
FROM information_schema.columns
WHERE table_name = 'features_wide'
ORDER BY ordinal_position;

-- 2. Identify MISSING required columns
SELECT unmatched.col AS missing_column
FROM (
    SELECT unnest(ARRAY[
        'returns', 'log_returns', 'rsi_14', 'macd', 'macd_signal',
        'vwap', 'sma_5', 'sma_20', 'ema_5', 'ema_12', 'ema_26',
        'bollinger_lower', 'bollinger_upper', 'rolling_volatility',
        'price_vs_vwap_pct', 'ema_spread_pct', 'relative_volume',
        'bollinger_band_position', 'volatility_regime', 'trend_strength'
    ]) AS col
) unmatched
LEFT JOIN information_schema.columns actual
    ON actual.table_name = 'features_wide'
    AND actual.column_name = unmatched.col
WHERE actual.column_name IS NULL;

-- 3. Count rows in features_wide
SELECT COUNT(*) AS row_count FROM features_wide;

-- 4. Check for NULL prevalence in normalized features
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE price_vs_vwap_pct IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_price_vs_vwap,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ema_spread_pct IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_ema_spread,
    ROUND(100.0 * COUNT(*) FILTER (WHERE relative_volume IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_rel_volume,
    ROUND(100.0 * COUNT(*) FILTER (WHERE bollinger_band_position IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_bb_position,
    ROUND(100.0 * COUNT(*) FILTER (WHERE volatility_regime IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_vol_regime,
    ROUND(100.0 * COUNT(*) FILTER (WHERE trend_strength IS NULL) / NULLIF(COUNT(*), 0), 2) AS pct_null_trend_strength
FROM features_wide;

-- 5. Sample: show one row with non-null normalized features
SELECT *
FROM features_wide
WHERE price_vs_vwap_pct IS NOT NULL
  AND ema_spread_pct IS NOT NULL
  AND relative_volume IS NOT NULL
  AND bollinger_band_position IS NOT NULL
  AND volatility_regime IS NOT NULL
  AND trend_strength IS NOT NULL
LIMIT 5;
