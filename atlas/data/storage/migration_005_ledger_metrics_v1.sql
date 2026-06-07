-- ============================================================================
-- P6 T6 — Additive v1 persistence surface (SHADOW STORE) for the Alpha Rebuild.
--
-- Holds the canonical-stack outputs WITHOUT touching the legacy stack:
--   ledger_metrics_v1     P1 ledger_metrics_v1 outputs (fractions)
--   strategy_scores_v1    P2 research_fitness / deploy_fitness + gate components
--   validator_results_v1  P3 validator_policy_v1 status (status_v1 — SHADOW ONLY)
--
-- STORAGE PRINCIPLES (enforced here):
--   * ADDITIVE ONLY — CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
--   * NO legacy table or column is altered or dropped.
--   * IDEMPOTENT — safe to run any number of times.
--   * NO authority switch / NO consumer cutover. Writing status_v1 here does NOT
--     modify strategies.status; nothing reads these tables yet.
--   * ROLLBACK = ignore (or DROP) these new tables; legacy behavior is unaffected.
--
-- Grain: one row per backtest window, keyed (strategy_id, start_date, end_date),
-- mirroring backtest_results' PK so a v1 row maps 1:1 to the window that produced
-- the trades. FK is to strategies(id) only (soft link to the window via the key)
-- to avoid coupling to backtest_results' storage/lifecycle.
-- ============================================================================

-- 1. ledger_metrics_v1 — P1 canonical metrics (ALL FRACTIONS; no ×100 anywhere)
CREATE TABLE IF NOT EXISTS ledger_metrics_v1 (
    strategy_id             UUID        NOT NULL,
    start_date              TIMESTAMPTZ NOT NULL,
    end_date                TIMESTAMPTZ NOT NULL,
    n_trades                INT         NOT NULL,
    total_return            NUMERIC,
    gross_edge              NUMERIC,
    cost_burden             NUMERIC,
    max_drawdown            NUMERIC,     -- fraction in [-1, 0]
    win_rate                NUMERIC,     -- [0, 1] per-trade
    profit_factor           NUMERIC,     -- per-trade, capped 5.0
    expectancy              NUMERIC,     -- per-trade mean net return
    sharpe                  NUMERIC,     -- per-trade ×√tpy, clamped [-10, 10]
    sortino                 NUMERIC,     -- clamped [-10, 10]
    calmar                  NUMERIC,
    avg_trade_duration_bars NUMERIC,
    metrics_version         TEXT        NOT NULL DEFAULT 'ledger_metrics_v1',
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_id, start_date, end_date),
    CONSTRAINT fk_ledger_metrics_v1_strategy
        FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ledger_metrics_v1_end
    ON ledger_metrics_v1 (end_date DESC);

-- 2. strategy_scores_v1 — P2 fitness (research = 100·Q, deploy = 100·Q·M)
CREATE TABLE IF NOT EXISTS strategy_scores_v1 (
    strategy_id      UUID        NOT NULL,
    start_date       TIMESTAMPTZ NOT NULL,
    end_date         TIMESTAMPTZ NOT NULL,
    research_fitness NUMERIC,     -- 100·Q   (ungated gradient)
    deploy_fitness   NUMERIC,     -- 100·Q·M (gated deployability)
    q                NUMERIC,     -- quality core Q
    m                NUMERIC,     -- deployability gate product M
    perf_q           NUMERIC,
    robust_q         NUMERIC,
    sig_gate         NUMERIC,
    overfit_gate     NUMERIC,
    cost_gate        NUMERIC,
    fitness_version  TEXT        NOT NULL DEFAULT 'fitness_v1',
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_id, start_date, end_date),
    CONSTRAINT fk_strategy_scores_v1_strategy
        FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_strategy_scores_v1_deploy
    ON strategy_scores_v1 (deploy_fitness DESC);

-- 3. validator_results_v1 — P3 status (status_v1 is SHADOW; NEVER strategies.status)
CREATE TABLE IF NOT EXISTS validator_results_v1 (
    strategy_id       UUID        NOT NULL,
    start_date        TIMESTAMPTZ NOT NULL,
    end_date          TIMESTAMPTZ NOT NULL,
    status_v1         TEXT        NOT NULL,  -- elite|validated|research_candidate|pending_validation|failed_validation
    deploy_fitness    NUMERIC,
    research_fitness  NUMERIC,
    n_trades          INT,
    coverage_complete BOOLEAN,
    structural_ok     BOOLEAN,
    policy_version    TEXT        NOT NULL DEFAULT 'validator_policy_v1',
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_id, start_date, end_date),
    CONSTRAINT fk_validator_results_v1_strategy
        FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_validator_results_v1_status
    ON validator_results_v1 (status_v1);
