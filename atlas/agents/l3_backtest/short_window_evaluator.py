"""
ShortWindowEvaluator — adaptive metrics for research-scale data windows.

When data is too shallow for statistically meaningful annualized Sharpe
(< 20,000 bars), this evaluator provides a composite score based on
raw returns, profit factor, win rate, drawdown, and trade count.

This prevents the sqrt(bars_per_year)=725 annualization factor from
amplifying tiny per-bar noise into extreme Sharpe values.
"""

import numpy as np
import pandas as pd


SHORT_WINDOW_THRESHOLD = 20_000


def is_short_window(df_or_length) -> bool:
    if isinstance(df_or_length, (int, float)):
        return df_or_length < SHORT_WINDOW_THRESHOLD
    return len(df_or_length) < SHORT_WINDOW_THRESHOLD


def compute_short_window_metrics(
    sub_df: pd.DataFrame,
    position_series: pd.Series,
    market_return: pd.Series,
    position_size: float = 0.10,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    spread_cost_pct: float = 0.0005,
    dynamic_slippage: np.ndarray | None = None,
) -> dict:
    if len(sub_df) == 0:
        return _zero_metrics()

    sub = sub_df.copy()
    sub["market_return"] = market_return
    sub["position"] = position_series

    per_side_base = commission_pct + slippage_pct + spread_cost_pct

    if dynamic_slippage is not None and len(dynamic_slippage) == len(sub):
        per_side_cost = per_side_base * dynamic_slippage
        total_roundtrip = per_side_cost * 2
    else:
        if dynamic_slippage is not None:
            import logging
            logging.getLogger(__name__).warning(
                f"Dynamic slippage length mismatch: {len(dynamic_slippage)} vs {len(sub)}, falling back to flat cost"
            )
        total_flat = per_side_base * 2
        total_roundtrip = np.full(len(sub), total_flat)

    sub["trade_cost"] = np.where(
        sub["position"].diff().fillna(0) != 0, total_roundtrip, 0.0
    )

    sub["strategy_return"] = (
        sub["position"] * sub["market_return"] * position_size
    ) - (sub["trade_cost"] * position_size)

    sub["cum_return"] = (1 + sub["strategy_return"]).cumprod()

    # Per-bar Sharpe ratio (correct: uses per-bar strategy_return, not per-trade PnL)
    strat_returns = sub["strategy_return"].values
    std = float(np.std(strat_returns))
    per_bar_sharpe = 0.0
    if std > 0 and len(strat_returns) > 0:
        mean_ret = float(np.mean(strat_returns))
        bars_per_year = 525600  # 365 * 24 * 60 (minutes)
        per_bar_sharpe = np.sqrt(bars_per_year) * (mean_ret / std)
        if np.isnan(per_bar_sharpe) or np.isinf(per_bar_sharpe):
            per_bar_sharpe = 0.0
        per_bar_sharpe = max(min(per_bar_sharpe, 10.0), -10.0)

    total_return = float(sub["cum_return"].iloc[-1] - 1)

    trades_bars = sub[sub["position"].diff().fillna(0) != 0]
    total_trades = len(trades_bars) // 2

    win_rate = 0.0
    profit_factor = 1.0
    avg_return_per_trade = 0.0
    max_drawdown = 0.0

    if total_trades > 0:
        winning = sub[sub["strategy_return"] > 0]
        losing = sub[sub["strategy_return"] < 0]
        total_nonzero = len(winning) + len(losing)
        if total_nonzero > 0:
            win_rate = len(winning) / total_nonzero

        gross_profit = winning["strategy_return"].sum()
        gross_loss = abs(losing["strategy_return"].sum())
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (10.0 if gross_profit > 0 else 1.0)
        )
        if np.isnan(profit_factor) or np.isinf(profit_factor):
            profit_factor = 1.0

        roll_max = sub["cum_return"].cummax()
        drawdown = sub["cum_return"] / roll_max - 1
        max_drawdown = float(drawdown.min())

        # Per-trade metrics from actual closed trades
        price_col = "close"
        pos_diff = sub["position"].diff().fillna(0)
        entry_bars = sub[pos_diff == 1].index
        exit_bars = sub[pos_diff == -1].index
        trade_pnls = []
        for e_idx, x_idx in zip(entry_bars[: len(exit_bars)], exit_bars):
            e_price = sub.loc[e_idx, price_col] if price_col in sub.columns else 0
            x_price = sub.loc[x_idx, price_col] if price_col in sub.columns else 0
            trade_pnls.append(float(x_price - e_price))
        if trade_pnls:
            avg_return_per_trade = float(np.mean(trade_pnls))
    else:
        # Even with 0 trades, compute basic metrics
        win_rate = 0.0
        profit_factor = 1.0
        max_drawdown = float(sub["cum_return"].min() - 1) if len(sub) > 0 else 0.0

    # Gross edge (no cost version)
    sub_no_cost = sub.copy()
    sub_no_cost["strat_no_cost"] = (
        sub_no_cost["position"] * sub_no_cost["market_return"] * position_size
    )
    sub_no_cost["cum_no_cost"] = (1 + sub_no_cost["strat_no_cost"]).cumprod()
    gross_edge = (
        float(sub_no_cost["cum_no_cost"].iloc[-1] - 1) if len(sub_no_cost) > 0 else 0.0
    )
    cost_burden = gross_edge - total_return

    return {
        "total_return": total_return,
        "gross_edge": gross_edge,
        "cost_burden": cost_burden,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_return_per_trade": avg_return_per_trade,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": per_bar_sharpe,
        "evaluation_mode": "short_window",
    }


def compute_composite_short_window_score(metrics: dict) -> float:
    raw_ret = metrics.get("total_return", 0.0)
    pf = metrics.get("profit_factor", 1.0)
    wr = metrics.get("win_rate", 0.0)
    dd = metrics.get("max_drawdown", 0.0)
    trades = metrics.get("total_trades", 0)
    cost_burden = metrics.get("cost_burden", 0.0)

    # 30% raw return — normalize: return / max(5%, abs(return)) gives range ~[-1, 1], map to [0, 1]
    r_norm = raw_ret / max(0.05, abs(raw_ret))
    r_score = max(0.0, min(1.0, (r_norm + 1.0) / 2.0))

    # 25% profit factor — cap at 3.0
    pf_score = max(0.0, min(1.0, (pf - 0.5) / 2.5))

    # 20% win rate — already [0, 1]
    wr_score = max(0.0, min(1.0, (wr - 0.3) / 0.5))

    # 15% max drawdown — less negative is better (0% DD → 1.0, -50% DD → 0.0)
    dd_score = max(0.0, min(1.0, 1.0 + dd / 0.50))

    # 10% trade count — more is better, cap at 50
    t_score = max(0.0, min(1.0, trades / 50.0))

    if trades == 0:
        return 0.0

    score = (
        r_score * 0.30
        + pf_score * 0.25
        + wr_score * 0.20
        + dd_score * 0.15
        + t_score * 0.10
    ) * 100

    return round(score, 1)


def _zero_metrics() -> dict:
    return {
        "total_return": 0.0,
        "gross_edge": 0.0,
        "cost_burden": 0.0,
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 1.0,
        "avg_return_per_trade": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
        "evaluation_mode": "short_window",
    }


def score_temporal_consistency(scores_by_window: list[float]) -> float:
    """
    Measures how consistent a strategy performs across time windows.
    Returns 0-1. Higher = more temporally consistent.
    """
    if len(scores_by_window) < 2:
        return 0.0
    import numpy as np
    arr = np.array(scores_by_window)
    mean_val = np.mean(arr)
    # Coefficient of variation (lower = more consistent)
    cv = np.std(arr) / (abs(mean_val) + 1e-8)
    # Convert to 0-1 score (cv=0 -> 1.0, cv>=1 -> 0.0)
    return float(max(0.0, 1.0 - cv))
