-- ============================================================
-- ATLAS DATABASE DIAGNOSTIC QUERIES
-- Run these to measure current data state before hardening
-- ============================================================

-- ============================================================
-- 1. PRECISION VIOLATIONS
-- ============================================================

-- Check market_data_l1 precision violations
SELECT COUNT(*) as precision_violations
FROM market_data_l1
WHERE 1=1
  OR ROUND(open::numeric, 4)::text != open::text
  OR ROUND(high::numeric, 4)::text != high::text
  OR ROUND(low::numeric, 4)::text != low::text
  OR ROUND(close::numeric, 4)::text != close::text;

-- Get sample precision violation rows
SELECT time, symbol, open, ROUND(open::numeric, 4) as rounded_open
FROM market_data_l1
WHERE ROUND(open::numeric, 4)::text != open::text
LIMIT 5;

-- Check for extreme precision in stored values
SELECT
  symbol,
  open,
  LENGTH(open::text) - POSITION('.' IN open::text) as decimal_places
FROM market_data_l1
WHERE POSITION('.' IN open::text) > 0
ORDER BY decimal_places DESC
LIMIT 10;

-- ============================================================
-- 2. UNIQUENESS VIOLATIONS (Duplicates)
-- ============================================================

-- market_data_l1: Check for duplicate (time, symbol) pairs
WITH dups AS (
  SELECT time, symbol, COUNT(*) as cnt
  FROM market_data_l1
  GROUP BY time, symbol
  HAVING COUNT(*) > 1
)
SELECT
  (SELECT COUNT(*) FROM dups) as duplicate_pairs,
  (SELECT SUM(cnt - 1) FROM dups) as extra_duplicate_rows;

-- Get sample duplicate pairs
SELECT time, symbol, COUNT(*) as cnt, MAX(ingestion_time) as latest_ingestion
FROM market_data_l1
GROUP BY time, symbol
HAVING COUNT(*) > 1
LIMIT 10;

-- execution_log: Check for duplicate order_key
WITH dups AS (
  SELECT order_key, COUNT(*) as cnt
  FROM execution_log
  GROUP BY order_key
  HAVING COUNT(*) > 1
)
SELECT
  (SELECT COUNT(*) FROM dups) as duplicate_order_keys,
  (SELECT SUM(cnt - 1) FROM dups) as extra_duplicate_records;

-- copy_execution_log: Check for duplicate (leader_order_id, follower_id)
WITH dups AS (
  SELECT leader_order_id, follower_id, COUNT(*) as cnt
  FROM copy_execution_log
  GROUP BY leader_order_id, follower_id
  HAVING COUNT(*) > 1
)
SELECT
  (SELECT COUNT(*) FROM dups) as duplicate_pairs,
  (SELECT SUM(cnt - 1) FROM dups) as extra_records;

-- ============================================================
-- 3. FOREIGN KEY VIOLATIONS (Orphaned Records)
-- ============================================================

-- backtest_results orphans
SELECT
  COUNT(*) as orphaned_backtest_results,
  COUNT(DISTINCT br.strategy_id) as orphaned_strategies
FROM backtest_results br
LEFT JOIN strategies s ON br.strategy_id = s.id
WHERE s.id IS NULL;

-- backtest_trades orphans
SELECT
  COUNT(*) as orphaned_backtest_trades,
  COUNT(DISTINCT bt.strategy_id) as orphaned_strategies
FROM backtest_trades bt
LEFT JOIN strategies s ON bt.strategy_id = s.id
WHERE s.id IS NULL;

-- performance_metrics orphans
SELECT
  COUNT(*) as orphaned_performance_metrics,
  COUNT(DISTINCT pm.strategy_id) as orphaned_strategies
FROM performance_metrics pm
LEFT JOIN strategies s ON pm.strategy_id = s.id
WHERE s.id IS NULL;

-- system_logs with missing agent_registry
SELECT
  COUNT(*) as orphaned_system_logs,
  COUNT(DISTINCT sl.agent_id) as orphaned_agents
FROM system_logs sl
LEFT JOIN agent_registry ar ON sl.agent_id = ar.id
WHERE ar.id IS NULL;

-- ============================================================
-- 4. ENUM VALIDATION (Invalid Values)
-- ============================================================

-- execution_log: Invalid state values
SELECT DISTINCT state, COUNT(*) as cnt
FROM execution_log
WHERE state NOT IN ('pending', 'partial_fill', 'filled', 'cancelled', 'rejected', 'expired')
GROUP BY state;

-- execution_log: Invalid side values
SELECT DISTINCT side, COUNT(*) as cnt
FROM execution_log
WHERE side NOT IN ('buy', 'sell')
GROUP BY side;

-- order_flow: Invalid side values
SELECT DISTINCT side, COUNT(*) as cnt
FROM order_flow
WHERE side NOT IN ('buy', 'sell')
GROUP BY side;

-- positions: Invalid side values
SELECT DISTINCT side, COUNT(*) as cnt
FROM positions
WHERE side NOT IN ('long', 'short')
GROUP BY side;

-- copy_execution_log: Invalid status values
SELECT DISTINCT status, COUNT(*) as cnt
FROM copy_execution_log
WHERE status NOT IN ('pending', 'filled', 'skipped', 'failed')
GROUP BY status;

-- paper_trades: Invalid status values
SELECT DISTINCT status, COUNT(*) as cnt
FROM paper_trades
WHERE status NOT IN ('pending', 'filled', 'cancelled', 'rejected')
GROUP BY status;

-- ============================================================
-- 5. NEGATIVE/ZERO VALUES (Range Violations)
-- ============================================================

-- Negative prices in market_data_l1
SELECT COUNT(*) as negative_prices
FROM market_data_l1
WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0;

-- Negative volume in market_data_l1
SELECT COUNT(*) as negative_volumes
FROM market_data_l1
WHERE volume < 0;

-- NULL volume in market_data_l1
SELECT COUNT(*) as null_volumes
FROM market_data_l1
WHERE volume IS NULL;

-- Negative prices in order_flow
SELECT COUNT(*) as negative_prices
FROM order_flow
WHERE price <= 0;

-- Negative sizes in order_flow
SELECT COUNT(*) as negative_sizes
FROM order_flow
WHERE size < 0;

-- Invalid sharpe in backtest_results
SELECT COUNT(*) as out_of_range_sharpe
FROM backtest_results
WHERE sharpe < -10 OR sharpe > 10;

-- Invalid win_rate
SELECT COUNT(*) as invalid_win_rate
FROM backtest_results
WHERE win_rate < 0 OR win_rate > 1;

-- Invalid max_drawdown
SELECT COUNT(*) as invalid_max_drawdown
FROM backtest_results
WHERE max_drawdown < -1 OR max_drawdown > 0;

-- ============================================================
-- 6. TEMPORAL VIOLATIONS
-- ============================================================

-- execution_log with future created_at
SELECT COUNT(*) as future_records
FROM execution_log
WHERE created_at > NOW();

-- strategies with future created_at
SELECT COUNT(*) as future_strategies
FROM strategies
WHERE created_at > NOW();

-- backtest_results with invalid date range
SELECT COUNT(*) as invalid_date_ranges
FROM backtest_results
WHERE start_date >= end_date;

-- backtest_trades with entry_time >= exit_time
SELECT COUNT(*) as invalid_trade_times
FROM backtest_trades
WHERE entry_time IS NOT NULL
  AND exit_time IS NOT NULL
  AND entry_time >= exit_time;

-- api_keys with revoked_at before created_at
SELECT COUNT(*) as invalid_revoke_times
FROM api_keys
WHERE revoked_at IS NOT NULL
  AND created_at > revoked_at;

-- ============================================================
-- 7. MISSING INDEXES (Performance Analysis)
-- ============================================================

-- Query performance without indexes (estimate)
-- Queries that need symbol index
SELECT 'market_data_l1 queries without symbol index' as issue,
  (SELECT COUNT(DISTINCT symbol) FROM market_data_l1) as unique_symbols,
  (SELECT COUNT(*) FROM market_data_l1) as total_rows,
  CASE
    WHEN (SELECT COUNT(*) FROM market_data_l1) > 1000000 THEN 'CRITICAL: Full table scan slow'
    ELSE 'ACCEPTABLE: Small dataset'
  END as severity;

-- Same for features table
SELECT 'features queries without symbol index' as issue,
  (SELECT COUNT(DISTINCT symbol) FROM features) as unique_symbols,
  (SELECT COUNT(*) FROM features) as total_rows,
  CASE
    WHEN (SELECT COUNT(*) FROM features) > 5000000 THEN 'CRITICAL: Full table scan slow'
    ELSE 'ACCEPTABLE: Moderate dataset'
  END as severity;

-- Ranking queries without indexes
SELECT 'backtest_results ranking without sharpe index' as issue,
  COUNT(*) as total_results,
  COUNT(DISTINCT strategy_id) as unique_strategies,
  CASE
    WHEN COUNT(*) > 10000 THEN 'CRITICAL: Sorting slow'
    ELSE 'ACCEPTABLE'
  END as severity
FROM backtest_results;

-- ============================================================
-- 8. STALE DATA DETECTION
-- ============================================================

-- Stale market data
SELECT
  symbol,
  MAX(time) as latest_bar,
  NOW() - MAX(time) as age,
  CASE
    WHEN NOW() - MAX(time) > INTERVAL '1 day' THEN 'VERY STALE'
    WHEN NOW() - MAX(time) > INTERVAL '1 hour' THEN 'STALE'
    ELSE 'FRESH'
  END as freshness
FROM market_data_l1
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY symbol
HAVING NOW() - MAX(time) > INTERVAL '1 hour'
ORDER BY age DESC;

-- Stale agent heartbeats
SELECT
  name,
  layer,
  status,
  last_heartbeat,
  NOW() - last_heartbeat as age,
  CASE
    WHEN NOW() - last_heartbeat > INTERVAL '10 minutes' THEN 'DEAD'
    WHEN NOW() - last_heartbeat > INTERVAL '5 minutes' THEN 'STALE'
    ELSE 'FRESH'
  END as health
FROM agent_registry
WHERE last_heartbeat < NOW() - INTERVAL '1 minute'
ORDER BY last_heartbeat DESC;

-- Unrefreshed features_wide (manual)
SELECT
  MAX(time) as latest_feature_time
FROM features
WHERE time > NOW() - INTERVAL '1 day';

-- (Compare with actual last_update of features_wide if possible)

-- ============================================================
-- 9. OPERATIONAL BACKLOG
-- ============================================================

-- Unresolved dead letters
SELECT
  severity,
  COUNT(*) as count,
  MIN(created_at) as oldest,
  MAX(created_at) as newest,
  NOW() - MIN(created_at) as age_of_oldest
FROM execution_dead_letter
WHERE resolved = FALSE
GROUP BY severity
ORDER BY severity DESC;

-- Dead letters by failure reason (top 10)
SELECT
  failure_reason,
  COUNT(*) as count,
  COUNT(*) FILTER (WHERE resolved = FALSE) as unresolved
FROM execution_dead_letter
GROUP BY failure_reason
ORDER BY count DESC
LIMIT 10;

-- ============================================================
-- 10. DATA QUALITY SUMMARY
-- ============================================================

-- Comprehensive audit
WITH audit AS (
  SELECT 'market_data_l1 duplicates' as check_name,
    (SELECT COUNT(*) FROM (
      SELECT 1 FROM market_data_l1
      GROUP BY time, symbol HAVING COUNT(*) > 1
    ) x) as violations
  UNION ALL
  SELECT 'execution_log duplicates',
    (SELECT COUNT(*) FROM (
      SELECT 1 FROM execution_log
      GROUP BY order_key HAVING COUNT(*) > 1
    ) x)
  UNION ALL
  SELECT 'backtest_results orphans',
    (SELECT COUNT(*) FROM backtest_results br
     LEFT JOIN strategies s ON br.strategy_id = s.id
     WHERE s.id IS NULL)
  UNION ALL
  SELECT 'invalid sharpe values',
    (SELECT COUNT(*) FROM backtest_results
     WHERE sharpe < -10 OR sharpe > 10)
  UNION ALL
  SELECT 'negative prices',
    (SELECT COUNT(*) FROM market_data_l1
     WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0)
  UNION ALL
  SELECT 'future records',
    (SELECT COUNT(*) FROM execution_log WHERE created_at > NOW())
  UNION ALL
  SELECT 'unresolved critical dead letters',
    (SELECT COUNT(*) FROM execution_dead_letter
     WHERE resolved = FALSE AND severity = 'critical'
     AND created_at < NOW() - INTERVAL '1 hour')
  UNION ALL
  SELECT 'stale agents (>10min)',
    (SELECT COUNT(*) FROM agent_registry
     WHERE status = 'running' AND last_heartbeat < NOW() - INTERVAL '10 minutes')
)
SELECT check_name, violations,
  CASE
    WHEN violations = 0 THEN '✅ PASS'
    WHEN violations < 10 THEN '⚠️ WARN'
    ELSE '🔴 FAIL'
  END as status
FROM audit
ORDER BY violations DESC;

-- ============================================================
-- 11. PERFORMANCE BASELINE (Before Optimization)
-- ============================================================

-- Query: Get top 100 strategies by sharpe (no index)
-- Time this to establish baseline
EXPLAIN ANALYZE
SELECT strategy_id, sharpe, created_at
FROM backtest_results
ORDER BY sharpe DESC NULLS LAST
LIMIT 100;

-- Query: Get all market data for symbol (no symbol index)
EXPLAIN ANALYZE
SELECT time, open, high, low, close, volume
FROM market_data_l1
WHERE symbol = 'BTC/USD'
ORDER BY time DESC
LIMIT 1000;

-- Query: Get execution logs by status (no state index)
EXPLAIN ANALYZE
SELECT id, order_key, symbol, state
FROM execution_log
WHERE state = 'filled'
ORDER BY created_at DESC
LIMIT 100;

-- ============================================================
-- FINAL REPORT: Copy-Paste Friendly
-- ============================================================

/*
ATLAS Database Audit - Current State Summary
Report Date: [Date]

CRITICAL ISSUES:
[ ] Duplicate (time, symbol) in market_data_l1: ___ rows
[ ] Orphaned backtest_results: ___ rows
[ ] Invalid precision values: ___ rows
[ ] Invalid enum values: ___ rows
[ ] Stale agents: ___ rows

SCORE BEFORE HARDENING:
Duplicates: ___ violations
Foreign Keys: ___ orphans
Precision: ___ violations
Enums: ___ violations
Performance: ___ missing indexes

RECOMMENDED IMMEDIATE ACTIONS:
1. Deploy Phase 1 hardening script
2. Monitor for constraint violations during deploy
3. Run Phase 2 indexes immediately after
4. Set up alerting for ongoing monitoring

*/
