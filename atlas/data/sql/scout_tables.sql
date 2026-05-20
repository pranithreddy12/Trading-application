-- ============================================================================
-- SCOUT NETWORK TABLES — Phase 10: Internal Scout Intelligence
-- ============================================================================
-- These tables persist scout intelligence for restart safety and cross-agent
-- consumption. All scouts inherit from BaseAgent and write to these tables.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE 1: market_regime_memory — Persistent regime classifications per symbol
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_regime_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT,
    asset_class TEXT,
    timeframe TEXT,
    timestamp TIMESTAMPTZ NOT NULL,

    -- Primary classifications
    volatility_regime TEXT,        -- low_vol, normal_vol, high_vol, panic_vol
    trend_regime TEXT,             -- trending_up, trending_down, mean_reverting, choppy
    liquidity_regime TEXT,         -- deep_liquid, normal, thin, dangerous
    correlation_regime TEXT,       -- diversified, clustered, panic_correlation, regime_break

    -- Numerical measurements
    atr_percentile NUMERIC,
    realized_volatility NUMERIC,
    relative_volume NUMERIC,
    spread_bps NUMERIC,

    -- Structural indicators
    compression_detected BOOLEAN,
    expansion_detected BOOLEAN,
    vwap_deviation_pct NUMERIC,

    -- Confidence & metadata
    confidence_score NUMERIC DEFAULT 0.0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_regime_memory_symbol ON market_regime_memory (symbol);
CREATE INDEX IF NOT EXISTS idx_regime_memory_timestamp ON market_regime_memory (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_regime_memory_vol_regime ON market_regime_memory (volatility_regime);
CREATE INDEX IF NOT EXISTS idx_regime_memory_trend_regime ON market_regime_memory (trend_regime);

-- ----------------------------------------------------------------------------
-- TABLE 2: liquidity_intelligence — Per-symbol liquidity measurements
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS liquidity_intelligence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT,
    timestamp TIMESTAMPTZ NOT NULL,

    -- Spread & depth
    avg_spread_bps NUMERIC,
    depth_imbalance NUMERIC,          -- bid_volume / ask_volume ratio
    liquidity_score NUMERIC,          -- 0-100 aggregate score
    slippage_risk NUMERIC,            -- 0-1, higher = more risk
    market_impact_estimate NUMERIC,   -- expected price impact of standard order

    -- Classification
    liquidity_regime TEXT,            -- excellent, stable, thin, dangerous

    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_liquidity_symbol ON liquidity_intelligence (symbol);
CREATE INDEX IF NOT EXISTS idx_liquidity_timestamp ON liquidity_intelligence (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_liquidity_regime ON liquidity_intelligence (liquidity_regime);

-- ----------------------------------------------------------------------------
-- TABLE 3: correlation_memory — Portfolio-level correlation intelligence
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS correlation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,

    -- Cluster analysis
    cluster_name TEXT,                -- e.g., "crypto_majors", "tech_equities"
    avg_pairwise_corr NUMERIC,        -- average correlation within cluster
    dominant_factor TEXT,             -- e.g., "BTC", "SPY", "VIX"
    risk_state TEXT,                  -- diversified, clustered, panic_correlation, regime_break

    -- Portfolio context
    symbols_analyzed TEXT[],          -- list of symbols in this cluster
    top_correlated_pairs JSONB,       -- {pair: correlation, ...}
    correlation_spike_detected BOOLEAN DEFAULT FALSE,

    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_correlation_timestamp ON correlation_memory (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_correlation_risk_state ON correlation_memory (risk_state);
CREATE INDEX IF NOT EXISTS idx_correlation_cluster ON correlation_memory (cluster_name);

-- ----------------------------------------------------------------------------
-- TABLE 4: execution_intelligence — Historical execution quality per symbol/broker
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_intelligence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,

    symbol TEXT,
    broker TEXT,

    -- Execution quality metrics
    avg_slippage_bps NUMERIC,
    fill_latency_ms NUMERIC,
    rejection_rate NUMERIC,
    fill_quality_score NUMERIC,       -- 0-100 aggregate

    -- Classification
    execution_regime TEXT,            -- optimal, degraded, stressed, unstable

    -- Context
    sample_size INT DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_execution_symbol ON execution_intelligence (symbol);
CREATE INDEX IF NOT EXISTS idx_execution_timestamp ON execution_intelligence (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_execution_regime ON execution_intelligence (execution_regime);
