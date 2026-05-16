-- Validate normalized feature persistence counts
-- Run AFTER backfill or live agent has cycled

-- 1. Count normalized features per symbol
SELECT symbol, feature_name, COUNT(*) AS row_count
FROM features
WHERE feature_name IN (
    'price_vs_vwap_pct',
    'ema_spread_pct',
    'relative_volume',
    'bollinger_band_position',
    'volatility_regime',
    'trend_strength'
)
GROUP BY symbol, feature_name
ORDER BY symbol, feature_name;

-- 2. Compare normalized vs legacy counts per symbol
WITH legacy AS (
    SELECT symbol, feature_name, COUNT(*) AS cnt
    FROM features
    WHERE feature_name IN ('returns', 'rsi_14', 'vwap')
    GROUP BY symbol, feature_name
),
normalized AS (
    SELECT symbol, feature_name, COUNT(*) AS cnt
    FROM features
    WHERE feature_name IN (
        'price_vs_vwap_pct',
        'ema_spread_pct',
        'relative_volume',
        'bollinger_band_position',
        'volatility_regime',
        'trend_strength'
    )
    GROUP BY symbol, feature_name
)
SELECT
    COALESCE(l.symbol, n.symbol) AS symbol,
    l.feature_name AS legacy_feature,
    l.cnt AS legacy_count,
    n.feature_name AS normalized_feature,
    n.cnt AS normalized_count,
    CASE
        WHEN l.cnt = n.cnt THEN 'OK'
        WHEN n.cnt IS NULL THEN 'MISSING'
        WHEN l.cnt > n.cnt THEN 'LAG'
        ELSE 'EXTRA'
    END AS status
FROM legacy l
FULL OUTER JOIN normalized n ON l.symbol = n.symbol
ORDER BY symbol, legacy_feature, normalized_feature;

-- 3. Find symbols with ANY normalized features (summary)
SELECT symbol, COUNT(DISTINCT feature_name) AS normalized_feature_count
FROM features
WHERE feature_name IN (
    'price_vs_vwap_pct',
    'ema_spread_pct',
    'relative_volume',
    'bollinger_band_position',
    'volatility_regime',
    'trend_strength'
)
GROUP BY symbol
ORDER BY symbol;
