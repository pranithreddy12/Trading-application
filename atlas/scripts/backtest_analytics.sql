/*
 * backtest_analytics.sql
 *
 * Analytics queries for backtest_trades table.
 * Provides intelligence feedback for Ideator improvements.
 *
 * Usage:
 *   psql -h localhost -p 5433 -U postgres -d atlas -f backtest_analytics.sql
 */

-- ==============================================================
-- 1. Average hold duration per strategy
-- ==============================================================
SELECT
    strategy_id,
    COUNT(*)                                            AS trade_count,
    ROUND(AVG(bars_held), 1)                            AS avg_bars_held,
    MIN(bars_held)                                      AS min_bars_held,
    MAX(bars_held)                                      AS max_bars_held
FROM backtest_trades
GROUP BY strategy_id
ORDER BY avg_bars_held DESC;

-- ==============================================================
-- 2. Long vs short performance
-- ==============================================================
SELECT
    strategy_id,
    side,
    COUNT(*)                                            AS trades,
    ROUND(AVG(pnl)::numeric, 4)                         AS avg_pnl,
    ROUND(AVG(pnl_pct)::numeric, 6)                     AS avg_pnl_pct,
    ROUND(SUM(pnl)::numeric, 4)                         AS total_pnl,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::numeric
        / NULLIF(COUNT(*), 0), 4)                        AS win_rate
FROM backtest_trades
GROUP BY strategy_id, side
ORDER BY strategy_id, side;

-- ==============================================================
-- 3. Exit reason distribution
-- ==============================================================
SELECT
    strategy_id,
    exit_reason,
    COUNT(*)                                            AS count,
    ROUND(AVG(pnl)::numeric, 4)                         AS avg_pnl
FROM backtest_trades
GROUP BY strategy_id, exit_reason
ORDER BY strategy_id, count DESC;

-- ==============================================================
-- 4. Symbol dependence per strategy
-- ==============================================================
SELECT
    strategy_id,
    symbol,
    COUNT(*)                                            AS trades,
    ROUND(AVG(pnl)::numeric, 4)                         AS avg_pnl,
    ROUND(SUM(pnl)::numeric, 4)                         AS total_pnl
FROM backtest_trades
GROUP BY strategy_id, symbol
ORDER BY strategy_id, total_pnl DESC;

-- ==============================================================
-- 5. Strategy regime fit (combine with backtest_results)
-- ==============================================================
SELECT
    b.strategy_id,
    s.name                                              AS strategy_name,
    b.sharpe,
    b.win_rate,
    b.total_trades,
    ROUND(AVG(t.pnl)::numeric, 6)                      AS avg_trade_pnl,
    ROUND(STDDEV(t.pnl)::numeric, 6)                    AS trade_pnl_stddev,
    ROUND(AVG(t.bars_held)::numeric, 1)                 AS avg_bars_held
FROM backtest_results b
JOIN backtest_trades t ON b.strategy_id = t.strategy_id
JOIN strategies s ON b.strategy_id = s.id
GROUP BY b.strategy_id, s.name, b.sharpe, b.win_rate, b.total_trades
ORDER BY b.sharpe DESC;

-- ==============================================================
-- 6. Top-performing symbols across all strategies
-- ==============================================================
SELECT
    symbol,
    COUNT(DISTINCT strategy_id)                         AS strategy_count,
    COUNT(*)                                            AS total_trades,
    ROUND(AVG(pnl)::numeric, 4)                         AS avg_pnl,
    ROUND(SUM(pnl)::numeric, 4)                         AS total_pnl,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::numeric
        / NULLIF(COUNT(*), 0), 4)                        AS win_rate
FROM backtest_trades
GROUP BY symbol
ORDER BY total_pnl DESC;
