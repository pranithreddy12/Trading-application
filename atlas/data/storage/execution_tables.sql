-- ============================================================
-- ATLAS Execution Layer — Schema Migration
-- Version: 1.0.0
-- Date: 2026-05-17
-- 
-- SAFETY:
--   - All statements are idempotent (IF NOT EXISTS / IF EXISTS)
--   - No destructive DROP/ALTER on existing tables
--   - Safe to re-run on existing database
--
-- ROLLBACK: see execution_tables_rollback.sql
-- ============================================================

-- 1. execution_log: Immutable append-only order state machine audit trail
CREATE TABLE IF NOT EXISTS execution_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_key       TEXT NOT NULL,
    strategy_id     UUID,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    quantity        NUMERIC,
    price           NUMERIC,
    state           TEXT NOT NULL,
    broker_order_id TEXT,
    client_order_id TEXT,
    broker          TEXT NOT NULL DEFAULT 'alpaca',
    error_message   TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for execution_log
CREATE INDEX IF NOT EXISTS idx_exec_log_order_key    ON execution_log(order_key);
CREATE INDEX IF NOT EXISTS idx_exec_log_strategy     ON execution_log(strategy_id);
CREATE INDEX IF NOT EXISTS idx_exec_log_state        ON execution_log(state);
CREATE INDEX IF NOT EXISTS idx_exec_log_created      ON execution_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_log_client_oid   ON execution_log(client_order_id);
CREATE INDEX IF NOT EXISTS idx_exec_log_broker_oid   ON execution_log(broker_order_id);

-- 2. execution_dead_letter: Failed orders requiring human review or replay
CREATE TABLE IF NOT EXISTS execution_dead_letter (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_key       TEXT NOT NULL,
    strategy_id     UUID,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    quantity        NUMERIC,
    failure_reason  TEXT NOT NULL,
    last_state      TEXT NOT NULL,
    broker_order_id TEXT,
    client_order_id TEXT,
    severity        TEXT NOT NULL DEFAULT 'medium',
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolution      TEXT,
    retry_count     INT NOT NULL DEFAULT 0,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- Index: unresolved dead letters (dashboard + alerting)
CREATE INDEX IF NOT EXISTS idx_dead_letter_unresolved
    ON execution_dead_letter(resolved) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_dead_letter_severity
    ON execution_dead_letter(severity);
CREATE INDEX IF NOT EXISTS idx_dead_letter_strategy
    ON execution_dead_letter(strategy_id);

-- 3b. risk_state: persistent kill-switch governance for restart safety
CREATE TABLE IF NOT EXISTS risk_state (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           TEXT NOT NULL,
    strategy_id     UUID NULL,
    halted          BOOLEAN NOT NULL DEFAULT FALSE,
    reason          TEXT,
    triggered_by    TEXT,
    activated_at    TIMESTAMPTZ,
    released_at     TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_state_scope ON risk_state(scope);

INSERT INTO risk_state (
    scope,
    halted,
    reason
)
VALUES (
    'portfolio',
    FALSE,
    'initial_state'
)
ON CONFLICT DO NOTHING;

-- 3. positions table upgrade: add strategy_id and broker columns
-- (positions table already exists with: id, account_ref, symbol, qty, avg_price, side, created_at, updated_at)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS strategy_id UUID;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS broker TEXT NOT NULL DEFAULT 'alpaca';
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl NUMERIC DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_positions_broker   ON positions(broker);

-- 4. Verification queries (run these after migration to confirm)
-- SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'execution_log';
-- SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'execution_dead_letter';
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'positions' AND column_name IN ('strategy_id', 'broker', 'unrealized_pnl');
