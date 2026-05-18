-- 1. market_data_l1
-- PRECISION NOTE: Consider adding CHECK constraints to cap stored precision:
--   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_open_prec  CHECK (open  = ROUND(open,  4));
--   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_high_prec  CHECK (high  = ROUND(high,  4));
--   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_low_prec   CHECK (low   = ROUND(low,   4));
--   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_close_prec CHECK (close = ROUND(close, 4));
--   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_vol_prec   CHECK (
--       CASE WHEN asset_class = 'crypto' THEN ROUND(volume, 6) ELSE ROUND(volume, 4) END = volume);
-- Safer NUMERIC types (non-destructive): NUMERIC(18,4) for OHLC, NUMERIC(24,6) for crypto volume, NUMERIC(18,4) for equity volume
CREATE TABLE IF NOT EXISTS market_data_l1 (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    source TEXT NOT NULL,
    interval TEXT NOT NULL,
    asset_class TEXT NOT NULL DEFAULT 'crypto',
    ingestion_time TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('market_data_l1', 'time', if_not_exists => TRUE);

-- 2. market_data_l2
-- PRECISION NOTE: Consider CHECK constraints:
--   ALTER TABLE market_data_l2 ADD CONSTRAINT chk_spread_prec    CHECK (spread    = ROUND(spread,    6));
--   ALTER TABLE market_data_l2 ADD CONSTRAINT chk_mid_price_prec CHECK (mid_price = ROUND(mid_price, 6));
CREATE TABLE IF NOT EXISTS market_data_l2 (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    spread NUMERIC NOT NULL,
    mid_price NUMERIC NOT NULL
);
SELECT create_hypertable('market_data_l2', 'time', if_not_exists => TRUE);

-- 3. order_flow
-- PRECISION NOTE: Consider CHECK constraints:
--   ALTER TABLE order_flow ADD CONSTRAINT chk_price_prec CHECK (price = ROUND(price, 6));
--   ALTER TABLE order_flow ADD CONSTRAINT chk_size_prec  CHECK (size  = ROUND(size,  4));
CREATE TABLE IF NOT EXISTS order_flow (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    side TEXT NOT NULL,
    aggressor TEXT NOT NULL
);
SELECT create_hypertable('order_flow', 'time', if_not_exists => TRUE);

-- 4. features
-- PRECISION NOTE: Consider CHECK constraint (EAV format — different rounding per feature):
--   ALTER TABLE features ADD CONSTRAINT chk_feature_value_prec CHECK (
--       CASE WHEN feature_name IN ('returns', 'log_returns')
--            THEN ROUND(value, 8) ELSE ROUND(value, 6)
--       END = value);
-- Safer NUMERIC type: NUMERIC(18,8) for general use
CREATE TABLE IF NOT EXISTS features (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    value NUMERIC NOT NULL
);
SELECT create_hypertable('features', 'time', if_not_exists => TRUE);

-- 4b. features_wide — materialized view for fast strategy execution
CREATE MATERIALIZED VIEW IF NOT EXISTS features_wide AS
SELECT
    time,
    symbol,
    MAX(CASE WHEN feature_name='returns'               THEN value END) AS returns,
    MAX(CASE WHEN feature_name='log_returns'           THEN value END) AS log_returns,
    MAX(CASE WHEN feature_name='rsi_14'                THEN value END) AS rsi_14,
    MAX(CASE WHEN feature_name='macd'                  THEN value END) AS macd,
    MAX(CASE WHEN feature_name='macd_signal'           THEN value END) AS macd_signal,
    MAX(CASE WHEN feature_name='vwap'                  THEN value END) AS vwap,
    MAX(CASE WHEN feature_name='sma_5'                 THEN value END) AS sma_5,
    MAX(CASE WHEN feature_name='sma_20'                THEN value END) AS sma_20,
    MAX(CASE WHEN feature_name='ema_5'                 THEN value END) AS ema_5,
    MAX(CASE WHEN feature_name='ema_12'                THEN value END) AS ema_12,
    MAX(CASE WHEN feature_name='ema_26'                THEN value END) AS ema_26,
    MAX(CASE WHEN feature_name='bollinger_lower'       THEN value END) AS bollinger_lower,
    MAX(CASE WHEN feature_name='bollinger_upper'       THEN value END) AS bollinger_upper,
    MAX(CASE WHEN feature_name='rolling_volatility'    THEN value END) AS rolling_volatility,
    MAX(CASE WHEN feature_name='price_vs_vwap_pct'     THEN value END) AS price_vs_vwap_pct,
    MAX(CASE WHEN feature_name='ema_spread_pct'        THEN value END) AS ema_spread_pct,
    MAX(CASE WHEN feature_name='relative_volume'       THEN value END) AS relative_volume,
    MAX(CASE WHEN feature_name='bollinger_band_position' THEN value END) AS bollinger_band_position,
    MAX(CASE WHEN feature_name='volatility_regime'     THEN value END) AS volatility_regime,
    MAX(CASE WHEN feature_name='trend_strength'        THEN value END) AS trend_strength
FROM features
GROUP BY time, symbol;
CREATE UNIQUE INDEX IF NOT EXISTS idx_features_wide_time_symbol ON features_wide (time, symbol);

-- 5. strategies (Relational table, not a hypertable)
CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    parameters JSONB NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    author_agent TEXT NOT NULL,
    prompt TEXT,
    raw_response TEXT,
    normalized_strategy JSONB,
    compile_error TEXT
);

-- 6. backtest_results (Relational table)
CREATE TABLE IF NOT EXISTS backtest_results (
    strategy_id UUID NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    sharpe NUMERIC,
    cagr NUMERIC,
    max_drawdown NUMERIC,
    win_rate NUMERIC,
    total_trades INT,
    passed_validation BOOLEAN,
    results JSONB,
    entry_count INT,
    exit_count INT,
    bars_processed INT,
    short_window_score NUMERIC,
    score_7d NUMERIC,
    score_14d NUMERIC,
    score_30d NUMERIC,
    PRIMARY KEY (strategy_id, start_date, end_date)
);

-- 7. backtest_trades
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    strategy_id UUID NOT NULL,
    symbol TEXT NOT NULL,
    entry_time TIMESTAMPTZ,
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC,
    exit_price NUMERIC,
    side TEXT,
    pnl NUMERIC,
    pnl_pct NUMERIC,
    bars_held INT,
    exit_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy ON backtest_trades (strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_entry ON backtest_trades (entry_time);

-- 8. paper_trades
CREATE TABLE IF NOT EXISTS paper_trades (
    time TIMESTAMPTZ NOT NULL,
    strategy_id UUID NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    fill_price NUMERIC,
    status TEXT NOT NULL,
    pnl NUMERIC
);
SELECT create_hypertable('paper_trades', 'time', if_not_exists => TRUE);

-- 10. agent_registry (Relational table)
CREATE TABLE IF NOT EXISTS agent_registry (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    layer TEXT NOT NULL,
    status TEXT NOT NULL,
    pid INT,
    last_heartbeat TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    metadata JSONB
);

-- 11. system_logs
CREATE TABLE IF NOT EXISTS system_logs (
    time TIMESTAMPTZ NOT NULL,
    agent_id UUID NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB
);
SELECT create_hypertable('system_logs', 'time', if_not_exists => TRUE);

-- 12. performance_metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    time TIMESTAMPTZ NOT NULL,
    strategy_id UUID NOT NULL,
    metric_name TEXT NOT NULL,
    value NUMERIC NOT NULL
);
SELECT create_hypertable('performance_metrics', 'time', if_not_exists => TRUE);

-- 13. intelligence_briefs
CREATE TABLE IF NOT EXISTS intelligence_briefs (
    id UUID PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL,
    brief_text TEXT NOT NULL,
    regime TEXT NOT NULL,
    strategies_count INT NOT NULL
);

-- 14. mutation_memory — tracks parent-child mutation lineage
CREATE TABLE IF NOT EXISTS mutation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_strategy_id UUID NOT NULL REFERENCES strategies(id),
    child_strategy_id UUID NOT NULL REFERENCES strategies(id),
    mutation_type TEXT NOT NULL,
    changed_fields TEXT[],
    parent_sharpe NUMERIC,
    child_sharpe NUMERIC,
    sharpe_delta NUMERIC,
    parent_entry_count INT,
    child_entry_count INT,
    parent_trades INT,
    child_trades INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mutation_memory_parent ON mutation_memory (parent_strategy_id);
CREATE INDEX IF NOT EXISTS idx_mutation_memory_child ON mutation_memory (child_strategy_id);

-- 15. combination_memory — tracks parent-child lineage for L2 combiner
CREATE TABLE IF NOT EXISTS combination_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_a UUID NOT NULL REFERENCES strategies(id),
    parent_b UUID NOT NULL REFERENCES strategies(id),
    child_id UUID REFERENCES strategies(id),
    combination_type TEXT NOT NULL,
    parent_a_sharpe NUMERIC,
    parent_b_sharpe NUMERIC,
    child_sharpe NUMERIC,
    sharpe_delta NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(parent_a, parent_b, combination_type)
);
CREATE INDEX IF NOT EXISTS idx_combination_memory_parent_a ON combination_memory (parent_a);
CREATE INDEX IF NOT EXISTS idx_combination_memory_parent_b ON combination_memory (parent_b);
CREATE INDEX IF NOT EXISTS idx_combination_memory_child ON combination_memory (child_id);

-- 16. lifecycle_events — Event Lineage Layer (Day 7b)
CREATE TABLE IF NOT EXISTS lifecycle_events (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    strategy_id TEXT,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    actor TEXT NOT NULL,
    parent_event_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lifecycle_trace ON lifecycle_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_strategy ON lifecycle_events (strategy_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_stage ON lifecycle_events (stage);

-- Add trace_id to strategies
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS trace_id TEXT;
CREATE INDEX IF NOT EXISTS idx_strategies_trace ON strategies (trace_id);
