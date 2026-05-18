-- ============================================================
-- ATLAS DATABASE SCHEMA HARDENING SCRIPTS
-- Phase 2: Enum & Index Hardening (Priority 2 - Next Sprint)
-- ============================================================
-- ⚠ BACKUP FIRST: pg_dump -h localhost -d atlas > backup_$(date +%Y%m%d).sql
-- ⚠ Indexes can impact ingestion performance; test with traffic
-- ============================================================

BEGIN;

-- ============================================================
-- 1. ADD ENUM CHECK CONSTRAINTS
-- ============================================================
-- Purpose: Prevent invalid enum values (side, status, state, etc.)

-- execution_log.state: Valid order states
ALTER TABLE execution_log
  ADD CONSTRAINT chk_execution_log_state
  CHECK (state IN (
    'pending',
    'partial_fill',
    'filled',
    'cancelled',
    'rejected',
    'expired'
  ));

-- execution_log.side: Buy or sell only
ALTER TABLE execution_log
  ADD CONSTRAINT chk_execution_log_side
  CHECK (side IN ('buy', 'sell'));

-- order_flow.side: Market side
ALTER TABLE order_flow
  ADD CONSTRAINT chk_order_flow_side
  CHECK (side IN ('buy', 'sell'));

-- positions.side: Position type
ALTER TABLE positions
  ADD CONSTRAINT chk_positions_side
  CHECK (side IN ('long', 'short'));

-- paper_trades.side: Trade side
ALTER TABLE paper_trades
  ADD CONSTRAINT chk_paper_trades_side
  CHECK (side IN ('buy', 'sell'));

-- paper_trades.status: Trade status
ALTER TABLE paper_trades
  ADD CONSTRAINT chk_paper_trades_status
  CHECK (status IN ('pending', 'filled', 'cancelled', 'rejected'));

-- execution_dead_letter.severity: Severity levels
ALTER TABLE execution_dead_letter
  ADD CONSTRAINT chk_execution_dead_letter_severity
  CHECK (severity IN ('low', 'medium', 'high', 'critical'));

-- copy_execution_log.status: Copy execution status
ALTER TABLE copy_execution_log
  ADD CONSTRAINT chk_copy_execution_log_status
  CHECK (status IN ('pending', 'filled', 'skipped', 'failed'));

-- api_keys.role: API role types
ALTER TABLE api_keys
  ADD CONSTRAINT chk_api_keys_role
  CHECK (role IN ('admin', 'trader', 'read_only', 'follower', 'monitor'));

-- audit_logs.status: Audit status
ALTER TABLE audit_logs
  ADD CONSTRAINT chk_audit_logs_status
  CHECK (status IN ('success', 'failure', 'denied'));

-- agent_registry.status: Agent status
ALTER TABLE agent_registry
  ADD CONSTRAINT chk_agent_registry_status
  CHECK (status IN ('running', 'stopped', 'error', 'initializing'));

-- market_data_l1.asset_class: Asset classification
ALTER TABLE market_data_l1
  ADD CONSTRAINT chk_market_data_l1_asset_class
  CHECK (asset_class IN ('crypto', 'equity'));

-- ============================================================
-- 2. CREATE MISSING INDEXES FOR QUERY PERFORMANCE
-- ============================================================
-- Purpose: Speed up frequently-used filters/sorts

-- Indexes on time-series tables for symbol filtering
CREATE INDEX IF NOT EXISTS idx_market_data_l1_symbol
  ON market_data_l1 (symbol)
  WHERE asset_class != 'unknown';

CREATE INDEX IF NOT EXISTS idx_market_data_l2_symbol
  ON market_data_l2 (symbol);

CREATE INDEX IF NOT EXISTS idx_order_flow_symbol
  ON order_flow (symbol);

CREATE INDEX IF NOT EXISTS idx_features_symbol_name
  ON features (symbol, feature_name);

CREATE INDEX IF NOT EXISTS idx_system_logs_agent_level
  ON system_logs (agent_id, level);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_metric_name
  ON performance_metrics (strategy_id, metric_name);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol_status
  ON paper_trades (symbol, status);

-- Indexes on catalog tables for ranking/sorting
CREATE INDEX IF NOT EXISTS idx_backtest_results_sharpe_desc
  ON backtest_results (sharpe DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_backtest_results_cagr_desc
  ON backtest_results (cagr DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_strategies_created_at_desc
  ON strategies (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategies_status
  ON strategies (status);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol
  ON backtest_trades (symbol);

-- Indexes on audit/operational tables
CREATE INDEX IF NOT EXISTS idx_execution_log_symbol_state
  ON execution_log (symbol, state);

CREATE INDEX IF NOT EXISTS idx_execution_dead_letter_unresolved
  ON execution_dead_letter (resolved, severity)
  WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS idx_copy_execution_log_symbol_status
  ON copy_execution_log (symbol, status);

CREATE INDEX IF NOT EXISTS idx_positions_account_symbol
  ON positions (account_ref, symbol);

CREATE INDEX IF NOT EXISTS idx_agent_registry_status
  ON agent_registry (status);

-- Indexes on lineage tables for traversal
CREATE INDEX IF NOT EXISTS idx_mutation_memory_mutation_type
  ON mutation_memory (mutation_type);

CREATE INDEX IF NOT EXISTS idx_combination_memory_combination_type
  ON combination_memory (combination_type);

CREATE INDEX IF NOT EXISTS idx_lifecycle_events_trace_id_created
  ON lifecycle_events (trace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_memory_confidence_score
  ON pattern_memory (confidence_score DESC, pattern_type);

-- Indexes for API audit and security
CREATE INDEX IF NOT EXISTS idx_api_request_audit_endpoint_status
  ON api_request_audit (endpoint, status_code);

CREATE INDEX IF NOT EXISTS idx_api_keys_active_role
  ON api_keys (is_active, role)
  WHERE revoked_at IS NULL;

-- ============================================================
-- 3. ADD TEMPORAL CONSTRAINTS
-- ============================================================

-- execution_log: created_at should be in reasonable past (not future)
ALTER TABLE execution_log
  ADD CONSTRAINT chk_execution_log_created_at_valid
  CHECK (created_at <= NOW());

-- strategies: created_at should be in reasonable past
ALTER TABLE strategies
  ADD CONSTRAINT chk_strategies_created_at_valid
  CHECK (created_at <= NOW());

-- backtest_results: start_date should be before end_date
ALTER TABLE backtest_results
  ADD CONSTRAINT chk_backtest_results_date_order
  CHECK (start_date < end_date);

-- backtest_trades: entry_time should be before exit_time (if both present)
ALTER TABLE backtest_trades
  ADD CONSTRAINT chk_backtest_trades_time_order
  CHECK (entry_time IS NULL OR exit_time IS NULL OR entry_time < exit_time);

-- api_keys: created_at should be before revoked_at
ALTER TABLE api_keys
  ADD CONSTRAINT chk_api_keys_revoke_order
  CHECK (revoked_at IS NULL OR created_at < revoked_at);

-- execution_dead_letter: created_at should be before resolved_at
ALTER TABLE execution_dead_letter
  ADD CONSTRAINT chk_dead_letter_resolve_order
  CHECK (resolved_at IS NULL OR created_at < resolved_at);

-- ============================================================
-- 4. CREATE MATERIALIZED VIEW FOR DATA QUALITY MONITORING
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_data_quality_summary AS
WITH table_stats AS (
  SELECT 'market_data_l1' as table_name, COUNT(*) as total_rows
  FROM market_data_l1
  UNION ALL
  SELECT 'features', COUNT(*) FROM features
  UNION ALL
  SELECT 'strategies', COUNT(*) FROM strategies
  UNION ALL
  SELECT 'execution_log', COUNT(*) FROM execution_log
  UNION ALL
  SELECT 'copy_execution_log', COUNT(*) FROM copy_execution_log
  UNION ALL
  SELECT 'backtest_results', COUNT(*) FROM backtest_results
),
recent_data AS (
  SELECT 'market_data_l1' as table_name, MAX(time) as last_update
  FROM market_data_l1
  WHERE time > NOW() - INTERVAL '7 days'
  UNION ALL
  SELECT 'features', MAX(time)
  FROM features
  WHERE time > NOW() - INTERVAL '7 days'
  UNION ALL
  SELECT 'execution_log', MAX(created_at)
  FROM execution_log
  WHERE created_at > NOW() - INTERVAL '7 days'
  UNION ALL
  SELECT 'copy_execution_log', MAX(created_at)
  FROM copy_execution_log
  WHERE created_at > NOW() - INTERVAL '7 days'
),
orphan_check AS (
  SELECT 'backtest_results orphans' as check_name, COUNT(*) as issues
  FROM backtest_results br
  LEFT JOIN strategies s ON br.strategy_id = s.id
  WHERE s.id IS NULL
  UNION ALL
  SELECT 'backtest_trades orphans', COUNT(*)
  FROM backtest_trades bt
  LEFT JOIN strategies s ON bt.strategy_id = s.id
  WHERE s.id IS NULL
  UNION ALL
  SELECT 'unresolved dead letters', COUNT(*)
  FROM execution_dead_letter
  WHERE resolved = FALSE AND created_at < NOW() - INTERVAL '1 hour'
)
SELECT
  ts.table_name,
  ts.total_rows,
  rd.last_update,
  NOW() - rd.last_update as staleness,
  CASE
    WHEN NOW() - rd.last_update > INTERVAL '1 day' THEN 'STALE'
    WHEN NOW() - rd.last_update > INTERVAL '1 hour' THEN 'OLD'
    ELSE 'FRESH'
  END as freshness_status
FROM table_stats ts
LEFT JOIN recent_data rd ON ts.table_name = rd.table_name
ORDER BY ts.table_name;

CREATE UNIQUE INDEX idx_mv_data_quality_summary
  ON mv_data_quality_summary (table_name);

-- ============================================================
-- 5. ADD CONSTRAINT THAT EXECUTION + POSITION ARE CONSISTENT
-- ============================================================
-- Purpose: Prevent position/order divergence

-- Note: PostgreSQL doesn't support deferred FK constraints easily
-- Best practice: enforce at application level with transaction
-- SQL version: soft check via view

CREATE VIEW v_order_position_mismatch AS
SELECT
  el.symbol,
  el.strategy_id,
  COUNT(*) as filled_count,
  SUM(CASE WHEN el.side = 'buy' THEN el.quantity ELSE -el.quantity END) as expected_qty,
  COALESCE(p.qty, 0) as actual_qty,
  el.symbol || '_' || COALESCE(el.strategy_id::text, 'none') as key
FROM execution_log el
LEFT JOIN positions p ON p.symbol = el.symbol AND p.strategy_id = el.strategy_id
WHERE el.state = 'filled'
GROUP BY el.symbol, el.strategy_id, p.qty
HAVING SUM(CASE WHEN el.side = 'buy' THEN el.quantity ELSE -el.quantity END) != COALESCE(p.qty, 0);

-- ============================================================
-- 6. ADD INDEXES FOR COMMON REPORTING QUERIES
-- ============================================================

-- Mutation leaderboard: group by mutation_type
CREATE INDEX IF NOT EXISTS idx_mutation_memory_type_improved
  ON mutation_memory (mutation_type, child_sharpe DESC NULLS LAST);

-- Strategy ranking: latest strategies ordered by sharpe
CREATE INDEX IF NOT EXISTS idx_strategies_backtest_ranking
  ON strategies (created_at DESC)
  WHERE status = 'validated';

-- Pattern detection: find winning patterns
CREATE INDEX IF NOT EXISTS idx_pattern_memory_winning
  ON pattern_memory (composite_score_avg DESC)
  WHERE pattern_type = 'winning_motif';

-- Copy trader latency analytics
CREATE INDEX IF NOT EXISTS idx_copy_execution_latency
  ON copy_execution_log (created_at DESC)
  WHERE status = 'filled';

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (Run after applying Phase 2)
-- ============================================================

-- Check all enum constraints applied
SELECT constraint_name, table_name, constraint_definition
FROM information_schema.check_constraints
WHERE constraint_name LIKE 'chk_%'
  AND constraint_name NOT LIKE 'chk_%.%'
ORDER BY table_name, constraint_name;

-- Check all new indexes created
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
  AND indexname NOT IN (
    SELECT constraint_name
    FROM information_schema.table_constraints
    WHERE constraint_type = 'PRIMARY KEY'
  )
ORDER BY tablename, indexname;

-- Check data quality materialized view
SELECT * FROM mv_data_quality_summary;

-- Check for mismatches
SELECT * FROM v_order_position_mismatch LIMIT 10;

-- ============================================================
-- PERFORMANCE IMPACT ANALYSIS
-- ============================================================
/*
Expected Performance Changes:

POSITIVE:
+ Symbol filtering queries 10-50x faster (new symbol indexes)
+ Ranking queries (sharpe, cagr) 5-10x faster
+ Execution status queries faster (state enum constraint)
+ Dead letter alerting faster (partial index on unresolved)

NEGATIVE:
- Inserts slightly slower (more constraints to check)
  ~5-10ms overhead per row with precision + range checks
- Storage slightly larger (additional indexes)
  ~500MB-1GB additional space for new indexes

MITIGATIONS:
- Run during off-peak hours (2-4am typically)
- Test with production-like traffic load in staging
- Consider REINDEX if indexes become fragmented
- Monitor query performance with EXPLAIN ANALYZE

Expected ingestion rate impact: <5% slowdown
Acceptable for operational gains.
*/

-- ============================================================
-- IF ROLLBACK NEEDED:
-- ============================================================
/*
DROP MATERIALIZED VIEW IF EXISTS mv_data_quality_summary;
DROP VIEW IF EXISTS v_order_position_mismatch;

-- Drop all indexes (selective)
DROP INDEX IF EXISTS idx_market_data_l1_symbol;
DROP INDEX IF EXISTS idx_backtest_results_sharpe_desc;
-- ... (continue for all new indexes)

-- Drop all CHECK constraints
ALTER TABLE execution_log DROP CONSTRAINT chk_execution_log_state;
-- ... (continue for all new constraints)
*/
