-- ATLAS PRECISION NORMALIZATION SCRIPT
-- Phase 1: Create safe materialized views before destructive updates
-- Phase 2: Perform conditional precision updates on core tables

-- ==============================================================================
-- PHASE 1: SAFE MATERIALIZED VIEWS (Pre-Update)
-- ==============================================================================
-- These views provide immediate clean data without altering the source tables.
-- Useful for testing and rollback comparison.

CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_l1_clean AS
SELECT
    time,
    symbol,
    ROUND(open::numeric, 4) AS open,
    ROUND(high::numeric, 4) AS high,
    ROUND(low::numeric, 4) AS low,
    ROUND(close::numeric, 4) AS close,
    CASE 
        WHEN asset_class = 'crypto' THEN ROUND(volume::numeric, 6)
        ELSE ROUND(volume::numeric, 4)
    END AS volume,
    source,
    interval,
    asset_class
FROM market_data_l1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_l1_clean_time_symbol ON market_data_l1_clean (time, symbol);

CREATE MATERIALIZED VIEW IF NOT EXISTS features_clean AS
SELECT
    time,
    symbol,
    feature_name,
    CASE
        WHEN feature_name IN ('returns', 'log_returns', 'price_vs_vwap_pct', 'ema_spread_pct', 'trend_strength') THEN ROUND(value::numeric, 8)
        WHEN feature_name LIKE 'rsi_%' THEN ROUND(value::numeric, 4)
        ELSE ROUND(value::numeric, 6)
    END AS value
FROM features;

CREATE UNIQUE INDEX IF NOT EXISTS idx_features_clean_time_symbol_name ON features_clean (time, symbol, feature_name);

-- ==============================================================================
-- PHASE 2: DESTRUCTIVE HISTORICAL UPDATES (Only run when confident)
-- ==============================================================================
-- DO NOT RUN THESE without a pg_dump backup!
-- Example: pg_dump atlas > atlas_pre_precision_backup.sql

/* 
-- UNCOMMENT TO EXECUTE

-- 1. Market Data L1
UPDATE market_data_l1
SET
    open = ROUND(open::numeric, 4),
    high = ROUND(high::numeric, 4),
    low = ROUND(low::numeric, 4),
    close = ROUND(close::numeric, 4),
    volume = CASE 
                WHEN asset_class = 'crypto' THEN ROUND(volume::numeric, 6)
                ELSE ROUND(volume::numeric, 4)
             END;

-- 2. Market Data L2 (Only spread and mid_price, ignore jsonb bids/asks)
UPDATE market_data_l2
SET
    spread = ROUND(spread::numeric, 6),
    mid_price = ROUND(mid_price::numeric, 6)
WHERE spread IS NOT NULL AND mid_price IS NOT NULL;

-- 3. Features (Conditional Precision)
UPDATE features
SET value = CASE
    WHEN feature_name IN ('returns', 'log_returns', 'price_vs_vwap_pct', 'ema_spread_pct', 'trend_strength') THEN ROUND(value::numeric, 8)
    WHEN feature_name LIKE 'rsi_%' THEN ROUND(value::numeric, 4)
    ELSE ROUND(value::numeric, 6)
END;
*/
