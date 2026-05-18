-- Day 4 idempotent migration: copy trading, lineage, validation metrics
-- Run this file with psql / any Postgres-compatible runner connected to the ATLAS DB.

-- NOTES:
-- 1) Idempotent: uses IF NOT EXISTS and IF NOT EXISTS for indexes/columns
-- 2) Uses gen_random_uuid() for UUID defaults (requires pgcrypto or pgcrypto-equivalent extension).
-- 3) Adds JSONB `validation_metrics` to `strategies` for flexible Day-4 metrics storage.

-- Ensure extension for gen_random_uuid exists (safe if already present)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- TABLE 1: copy_leader_accounts
CREATE TABLE IF NOT EXISTS copy_leader_accounts (
    leader_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker TEXT NOT NULL,
    account_ref TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_copy_leader_accounts_account_ref ON copy_leader_accounts (account_ref);

-- TABLE 2: copy_follower_accounts
CREATE TABLE IF NOT EXISTS copy_follower_accounts (
    follower_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_id UUID NOT NULL REFERENCES copy_leader_accounts(leader_id) ON DELETE CASCADE,
    broker TEXT NOT NULL,
    account_ref TEXT NOT NULL,
    allocation_ratio NUMERIC(5,4) NOT NULL DEFAULT 1.0,
    max_position_pct NUMERIC(5,4) NOT NULL DEFAULT 0.10,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_copy_follower_accounts_leader_id ON copy_follower_accounts (leader_id);

-- TABLE 3: leader_orders (source of truth for leader fills that trigger copy orders)
CREATE TABLE IF NOT EXISTS leader_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty NUMERIC NOT NULL,
    price NUMERIC,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_leader_orders_account_ref ON leader_orders (account_ref);
CREATE INDEX IF NOT EXISTS idx_leader_orders_created_at ON leader_orders (created_at DESC);

-- TABLE 4: copy_execution_log
CREATE TABLE IF NOT EXISTS copy_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_order_id UUID,
    follower_order_id UUID,
    leader_id UUID,
    follower_id UUID,
    symbol TEXT,
    side TEXT,
    leader_qty NUMERIC,
    follower_qty NUMERIC,
    latency_ms BIGINT,
    status TEXT,
    failure_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_copy_execution_log_created_at ON copy_execution_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_copy_execution_log_leader_id ON copy_execution_log (leader_id);

-- TABLE 5: strategy_lineage
CREATE TABLE IF NOT EXISTS strategy_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID,
    child_id UUID,
    source_type TEXT,
    mutation_type TEXT,
    performance_delta NUMERIC,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_strategy_lineage_parent ON strategy_lineage (parent_id);
CREATE INDEX IF NOT EXISTS idx_strategy_lineage_child ON strategy_lineage (child_id);

-- OPTIONAL: validation metrics storage (JSONB) — preferred for flexibility
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS validation_metrics JSONB;

-- Optional convenience numeric columns (only add if you want typed access)
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS train_sharpe NUMERIC;
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS test_sharpe NUMERIC;
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS holdout_sharpe NUMERIC;
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS stability_score NUMERIC;
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS overfit_flag BOOLEAN;
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS regime_score NUMERIC;

-- Index strategy signature for faster dedup checks
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS strategy_signature TEXT;
CREATE INDEX IF NOT EXISTS idx_strategies_signature ON strategies (strategy_signature);

-- Verification queries (examples):
-- Count rows
-- SELECT 'copy_leader_accounts' AS table, COUNT(*) FROM copy_leader_accounts;
-- SELECT 'copy_follower_accounts' AS table, COUNT(*) FROM copy_follower_accounts;
-- SELECT 'copy_execution_log' AS table, COUNT(*) FROM copy_execution_log;
-- Latency average (last day):
-- SELECT AVG(latency_ms) FROM copy_execution_log WHERE created_at > NOW() - INTERVAL '1 day';
-- Check validation metrics presence:
-- SELECT COUNT(*) FROM strategies WHERE validation_metrics IS NOT NULL;

-- Rollback notes (manual):
-- To rollback remove the tables added (data will be lost):
-- DROP TABLE IF EXISTS copy_execution_log CASCADE;
-- DROP TABLE IF EXISTS copy_follower_accounts CASCADE;
-- DROP TABLE IF EXISTS copy_leader_accounts CASCADE;
-- DROP TABLE IF EXISTS strategy_lineage CASCADE;
-- ALTER TABLE strategies DROP COLUMN IF EXISTS validation_metrics;

-- End of migration
