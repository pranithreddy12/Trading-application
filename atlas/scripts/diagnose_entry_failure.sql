-- ================================================================
-- DIAGNOSE SYSTEMIC ENTRY FAILURE (entry_count = 0)
-- ================================================================

-- 1. What conditions are strategies actually using?
SELECT
    name,
    parameters->'entry_conditions' AS entry_conditions,
    parameters->'exit_conditions' AS exit_conditions,
    status
FROM strategies
WHERE status IN ('pending_validation', 'validated_A', 'validated_B', 'failed_validation')
ORDER BY created_at DESC
LIMIT 30;

-- 2. What generated code looks like (first 5)
SELECT
    name,
    LEFT(code, 800) AS code_snippet
FROM strategies
WHERE code != ''
ORDER BY created_at DESC
LIMIT 5;

-- 3. ACTUAL feature ranges in DB — match these vs Ideator thresholds
SELECT
    feature_name,
    MIN(value) AS min_val,
    MAX(value) AS max_val,
    AVG(value) AS avg_val,
    COUNT(*) AS row_count,
    COUNT(DISTINCT value < 1 AND value > -1 OR NULL) AS pct_between_neg1_and_1
FROM features
WHERE symbol = 'NVDA'
  AND feature_name IN (
    'rsi_14',
    'price_vs_vwap_pct',
    'trend_strength',
    'relative_volume',
    'bollinger_band_position',
    'volatility_regime',
    'ema_spread_pct'
  )
GROUP BY feature_name
ORDER BY feature_name;

-- 4. Same for crypto
SELECT
    feature_name,
    MIN(value) AS min_val,
    MAX(value) AS max_val,
    AVG(value) AS avg_val,
    COUNT(*) AS row_count
FROM features
WHERE symbol = 'SOLUSDT'
  AND feature_name IN (
    'rsi_14',
    'price_vs_vwap_pct',
    'trend_strength',
    'relative_volume',
    'bollinger_band_position',
    'volatility_regime',
    'ema_spread_pct'
  )
GROUP BY feature_name
ORDER BY feature_name;

-- 5. CRITICAL: Check if RSI is stored 0-100 or 0-1
SELECT
    feature_name,
    MIN(value) AS min_val,
    MAX(value) AS max_val,
    CASE WHEN MAX(value) <= 1 THEN '0-1 scale' ELSE '0-100 scale' END AS scale
FROM features
WHERE feature_name = 'rsi_14'
  AND symbol = 'NVDA'
GROUP BY feature_name;

-- 6. Count NULLs in features_wide for normalized features
SELECT
    COUNT(*) AS total_rows,
    COUNT(price_vs_vwap_pct) AS price_vs_vwap_pct_nonnull,
    COUNT(trend_strength) AS trend_strength_nonnull,
    COUNT(relative_volume) AS relative_volume_nonnull,
    COUNT(bollinger_band_position) AS bollinger_band_position_nonnull,
    COUNT(volatility_regime) AS volatility_regime_nonnull,
    COUNT(ema_spread_pct) AS ema_spread_pct_nonnull,
    COUNT(rsi_14) AS rsi_14_nonnull
FROM features_wide
WHERE symbol = 'NVDA';

-- 7. Backtest results with entry_count
SELECT
    s.name,
    b.sharpe,
    b.total_trades,
    b.results->>'entry_count' AS entry_count,
    b.results->>'exit_count' AS exit_count,
    b.results->>'bars_processed' AS bars,
    s.status
FROM strategies s
JOIN backtest_results b ON s.id = b.strategy_id
WHERE s.status IN ('pending_validation', 'validated_A', 'validated_B', 'failed_validation')
ORDER BY b.created_at DESC
LIMIT 20;
