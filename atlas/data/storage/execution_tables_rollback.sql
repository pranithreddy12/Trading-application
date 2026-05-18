-- ============================================================
-- ATLAS Execution Layer — Schema Rollback
-- Undoes execution_tables.sql migration
-- 
-- WARNING: This drops execution audit data permanently.
-- Only use in emergency rollback scenarios.
-- ============================================================

DROP TABLE IF EXISTS execution_dead_letter;
DROP TABLE IF EXISTS execution_log;

-- Revert positions table columns (safe: leaves existing data intact)
ALTER TABLE positions DROP COLUMN IF EXISTS strategy_id;
ALTER TABLE positions DROP COLUMN IF EXISTS broker;
ALTER TABLE positions DROP COLUMN IF EXISTS unrealized_pnl;

DROP INDEX IF EXISTS idx_positions_strategy;
DROP INDEX IF EXISTS idx_positions_broker;
