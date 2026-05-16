/*
 * migration_001_precision_rounding.sql
 *
 * Rounds existing NUMERIC data in TimescaleDB to safe precision levels.
 *
 * ⚠ BACKUP FIRST:
 *    pg_dump -h localhost -p 5433 -U postgres -d atlas \
 *      --table=market_data_l1 --table=market_data_l2 \
 *      --table=order_flow --table=features \
 *      > atlas_pre_rounding_backup_$(date +%Y%m%d).sql
 *
 * ⚠ Rollback:
 *    psql -h localhost -p 5433 -U postgres -d atlas < backup_file.sql
 *
 * PRECISION TARGETS:
 *   - OHLC (market_data_l1):                  4 decimals
 *   - Volume (equity, market_data_l1):         4 decimals
 *   - Volume (crypto, market_data_l1):         6 decimals
 *   - Spread / mid_price (market_data_l2):     6 decimals
 *   - Trade price (order_flow):                6 decimals
 *   - Trade size (order_flow):                 4 decimals
 *   - Feature values (features):               6 decimals
 *   - Returns / log_returns (features):        8 decimals
 */

BEGIN;

-- ============================================================
-- 1. market_data_l1 — OHLCV rounding
-- ============================================================
-- Round OHLC to 4 decimals unconditionally
UPDATE market_data_l1
SET
    open  = ROUND(open::numeric, 4),
    high  = ROUND(high::numeric, 4),
    low   = ROUND(low::numeric, 4),
    close = ROUND(close::numeric, 4),
    volume = CASE
        WHEN asset_class = 'crypto' THEN ROUND(volume::numeric, 6)
        ELSE ROUND(volume::numeric, 4)
    END
WHERE TRUE;

-- ============================================================
-- 2. market_data_l2 — spread / mid_price
-- ============================================================
UPDATE market_data_l2
SET
    spread    = ROUND(spread::numeric, 6),
    mid_price = ROUND(mid_price::numeric, 6)
WHERE TRUE;

-- ============================================================
-- 3. order_flow — trade price / size
-- ============================================================
UPDATE order_flow
SET
    price = ROUND(price::numeric, 6),
    size  = ROUND(size::numeric, 4)
WHERE TRUE;

-- ============================================================
-- 4. features — value column (EAV format)
-- ============================================================
UPDATE features
SET value = CASE
    WHEN feature_name IN ('returns', 'log_returns') THEN ROUND(value::numeric, 8)
    ELSE ROUND(value::numeric, 6)
END
WHERE TRUE;

-- ============================================================
-- 5. Refresh materialized view
-- ============================================================
REFRESH MATERIALIZED VIEW CONCURRENTLY features_wide;

COMMIT;
