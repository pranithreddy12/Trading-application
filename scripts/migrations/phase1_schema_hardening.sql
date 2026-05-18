-- ============================================================
-- ATLAS DATABASE SCHEMA HARDENING SCRIPTS
-- Phase 1: Critical Constraints (Priority 1 - Deploy First)
-- ============================================================
-- ⚠ BACKUP FIRST: pg_dump -h localhost -d atlas > backup_$(date +%Y%m%d).sql
-- ⚠ Test in staging first!
-- ============================================================

BEGIN;

-- ============================================================
-- 1. ADD UNIQUE CONSTRAINTS ON CORE KEYS
-- ============================================================
-- Purpose: Prevent duplicate ingestion/orders

-- market_data_l1: Prevent duplicate bars for (time, symbol)
ALTER TABLE market_data_l1 ADD CONSTRAINT uniq_market_data_l1_time_symbol
  UNIQUE (time, symbol);

-- execution_log: Prevent duplicate order logging
ALTER TABLE execution_log ADD CONSTRAINT uniq_execution_log_order_key
  UNIQUE (order_key);

-- copy_execution_log: Prevent duplicate copy execution records
ALTER TABLE copy_execution_log ADD CONSTRAINT uniq_copy_exec_leader_follower
  UNIQUE (leader_order_id, follower_id);

-- ============================================================
-- 2. ADD FOREIGN KEY CONSTRAINTS
-- ============================================================
-- Purpose: Maintain referential integrity; cascade delete orphans

-- backtest_results → strategies
ALTER TABLE backtest_results
  ADD CONSTRAINT fk_backtest_results_strategy
  FOREIGN KEY (strategy_id)
  REFERENCES strategies(id)
  ON DELETE CASCADE;

-- backtest_trades → strategies
ALTER TABLE backtest_trades
  ADD CONSTRAINT fk_backtest_trades_strategy
  FOREIGN KEY (strategy_id)
  REFERENCES strategies(id)
  ON DELETE CASCADE;

-- performance_metrics → strategies
ALTER TABLE performance_metrics
  ADD CONSTRAINT fk_performance_metrics_strategy
  FOREIGN KEY (strategy_id)
  REFERENCES strategies(id)
  ON DELETE CASCADE;

-- lifecycle_events → strategies (after fixing type mismatch)
-- Note: Requires type conversion first; see Phase 1.5

-- ============================================================
-- 3. ADD NOT NULL CONSTRAINTS
-- ============================================================

-- market_data_l1.volume should never be NULL
ALTER TABLE market_data_l1 ALTER COLUMN volume SET NOT NULL;

-- order_flow.price and size should never be NULL
ALTER TABLE order_flow ALTER COLUMN price SET NOT NULL;
ALTER TABLE order_flow ALTER COLUMN size SET NOT NULL;

-- positions.qty should never be NULL (use 0 for closed)
ALTER TABLE positions ALTER COLUMN qty SET NOT NULL;

-- ============================================================
-- 4. ADD PRECISION CHECK CONSTRAINTS
-- ============================================================
-- Purpose: Enforce stored data matches expected precision

-- market_data_l1: OHLC to 4 decimals
ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_open_precision
  CHECK (ROUND(open::numeric, 4) = open);

ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_high_precision
  CHECK (ROUND(high::numeric, 4) = high);

ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_low_precision
  CHECK (ROUND(low::numeric, 4) = low);

ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_close_precision
  CHECK (ROUND(close::numeric, 4) = close);

-- market_data_l1: Volume precision (crypto 6dp, equity 4dp)
ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_volume_precision
  CHECK (
    CASE
      WHEN asset_class = 'crypto' THEN ROUND(volume::numeric, 6) = volume
      ELSE ROUND(volume::numeric, 4) = volume
    END
  );

-- market_data_l2: Spread and mid_price to 6 decimals
ALTER TABLE market_data_l2
  ADD CONSTRAINT chk_market_data_l2_spread_precision
  CHECK (ROUND(spread::numeric, 6) = spread);

ALTER TABLE market_data_l2
  ADD CONSTRAINT chk_market_data_l2_mid_price_precision
  CHECK (ROUND(mid_price::numeric, 6) = mid_price);

-- order_flow: Price to 6dp, size to 4dp
ALTER TABLE order_flow
  ADD CONSTRAINT chk_order_flow_price_precision
  CHECK (ROUND(price::numeric, 6) = price);

ALTER TABLE order_flow
  ADD CONSTRAINT chk_order_flow_size_precision
  CHECK (ROUND(size::numeric, 4) = size);

-- features: Value precision (6dp default, 8dp for returns)
ALTER TABLE features
  ADD CONSTRAINT chk_features_value_precision
  CHECK (
    CASE
      WHEN feature_name IN ('returns', 'log_returns', 'trend_strength', 'price_vs_vwap_pct', 'ema_spread_pct')
        THEN ROUND(value::numeric, 8) = value
      ELSE ROUND(value::numeric, 6) = value
    END
  );

-- ============================================================
-- 5. ADD VALUE RANGE CHECK CONSTRAINTS
-- ============================================================

-- Prices should never be zero or negative
ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_prices_positive
  CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0);

ALTER TABLE market_data_l2
  ADD CONSTRAINT chk_market_data_l2_prices_positive
  CHECK (spread >= 0 AND mid_price > 0);

ALTER TABLE order_flow
  ADD CONSTRAINT chk_order_flow_price_positive
  CHECK (price > 0);

-- Volume should be non-negative
ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_volume_nonnegative
  CHECK (volume >= 0);

ALTER TABLE order_flow
  ADD CONSTRAINT chk_order_flow_size_nonnegative
  CHECK (size >= 0);

-- backtest_results: Reasonable ranges for metrics
ALTER TABLE backtest_results
  ADD CONSTRAINT chk_backtest_results_sharpe_range
  CHECK (sharpe >= -10 AND sharpe <= 10 OR sharpe IS NULL);

ALTER TABLE backtest_results
  ADD CONSTRAINT chk_backtest_results_cagr_range
  CHECK (cagr >= -1 AND cagr <= 10 OR cagr IS NULL);

ALTER TABLE backtest_results
  ADD CONSTRAINT chk_backtest_results_max_drawdown_range
  CHECK (max_drawdown >= -1 AND max_drawdown <= 0 OR max_drawdown IS NULL);

ALTER TABLE backtest_results
  ADD CONSTRAINT chk_backtest_results_win_rate_range
  CHECK (win_rate >= 0 AND win_rate <= 1 OR win_rate IS NULL);

-- positions: qty can be negative (short) but not unreasonably large
ALTER TABLE positions
  ADD CONSTRAINT chk_positions_qty_reasonable
  CHECK (qty >= -999999 AND qty <= 999999);

-- Copy trading: allocation_ratio should be positive
ALTER TABLE copy_follower_accounts
  ADD CONSTRAINT chk_copy_follower_allocation_positive
  CHECK (allocation_ratio > 0);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (Run after applying constraints)
-- ============================================================

-- Verify UNIQUE constraints applied
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE constraint_name IN (
  'uniq_market_data_l1_time_symbol',
  'uniq_execution_log_order_key',
  'uniq_copy_exec_leader_follower'
)
ORDER BY constraint_name;

-- Verify FK constraints applied
SELECT constraint_name, table_name
FROM information_schema.table_constraints
WHERE constraint_name LIKE 'fk_%'
ORDER BY constraint_name;

-- Verify CHECK constraints applied
SELECT constraint_name, table_name
FROM information_schema.table_constraints
WHERE constraint_type = 'CHECK'
ORDER BY table_name, constraint_name;

-- ============================================================
-- IF ROLLBACK NEEDED:
-- ============================================================
/*
ALTER TABLE market_data_l1 DROP CONSTRAINT uniq_market_data_l1_time_symbol;
ALTER TABLE execution_log DROP CONSTRAINT uniq_execution_log_order_key;
ALTER TABLE copy_execution_log DROP CONSTRAINT uniq_copy_exec_leader_follower;
ALTER TABLE backtest_results DROP CONSTRAINT fk_backtest_results_strategy;
ALTER TABLE backtest_trades DROP CONSTRAINT fk_backtest_trades_strategy;
ALTER TABLE performance_metrics DROP CONSTRAINT fk_performance_metrics_strategy;
ALTER TABLE market_data_l1 ALTER COLUMN volume DROP NOT NULL;
-- ... (all CHECK constraints follow similar pattern)
*/
