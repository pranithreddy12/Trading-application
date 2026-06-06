/*
 * migration_003_strategy_performance.sql
 *
 * Creates strategy_performance table for computed paper trading metrics
 * and strategy_promotion_audit for qualification audit trail.
 *
 * These tables power the Paper Performance dashboard page.
 */

BEGIN;

-- ============================================================
-- 1. strategy_performance — computed metrics per strategy
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Return metrics
    daily_return_pct NUMERIC,
    weekly_return_pct NUMERIC,
    monthly_return_pct NUMERIC,
    rolling_30d_return_pct NUMERIC,
    total_return_pct NUMERIC,

    -- PnL
    realized_pnl NUMERIC,
    unrealized_pnl NUMERIC,

    -- Risk metrics
    sharpe_ratio NUMERIC,
    profit_factor NUMERIC,
    win_rate NUMERIC,
    max_drawdown_pct NUMERIC,

    -- Trade stats
    avg_trade_pnl NUMERIC,
    total_trades INT,

    -- Governance
    is_qualified BOOLEAN DEFAULT FALSE,
    qualified_at TIMESTAMPTZ,

    UNIQUE (strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_strat_perf_monthly ON strategy_performance (monthly_return_pct DESC);
CREATE INDEX IF NOT EXISTS idx_strat_perf_sharpe ON strategy_performance (sharpe_ratio DESC);
CREATE INDEX IF NOT EXISTS idx_strat_perf_qualified ON strategy_performance (is_qualified) WHERE is_qualified = TRUE;

-- ============================================================
-- 2. strategy_promotion_audit — qualification audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_promotion_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    result TEXT NOT NULL CHECK (result IN ('PASS', 'FAIL')),
    monthly_return_pct NUMERIC,
    sharpe_ratio NUMERIC,
    profit_factor NUMERIC,
    max_drawdown_pct NUMERIC,
    total_trades INT,
    fail_reasons JSONB DEFAULT '[]'::jsonb,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_promo_audit_strategy ON strategy_promotion_audit (strategy_id);
CREATE INDEX IF NOT EXISTS idx_promo_audit_result ON strategy_promotion_audit (result);
CREATE INDEX IF NOT EXISTS idx_promo_audit_time ON strategy_promotion_audit (checked_at DESC);

COMMIT;
