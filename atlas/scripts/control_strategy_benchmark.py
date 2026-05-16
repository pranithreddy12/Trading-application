"""
Control Strategy Benchmark — Short-Window Mode
Certifies backtest engine with known-good hand-written strategies,
now using ShortWindowEvaluator to avoid annualization distortion.

Extended with Buy & Hold, VWAP pullback, Low-frequency trend filter,
cost_efficiency_ratio, per-window breakdown, and DB persistence.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from atlas.agents.l3_backtest.short_window_evaluator import (
    compute_short_window_metrics,
    compute_composite_short_window_score,
)
from atlas.config.settings import get_settings


async def get_connection():
    import asyncpg

    settings = get_settings()
    url = settings.database_url  # postgresql+asyncpg://user:pass@host:port/db
    parts = url.replace("postgresql+asyncpg://", "").split("/")
    dbname = parts[1]
    user_pass_host = parts[0].split("@")
    user_pass = user_pass_host[0].split(":")
    host_port = user_pass_host[1].split(":")
    return await asyncpg.connect(
        user=user_pass[0],
        password=user_pass[1],
        host=host_port[0],
        port=int(host_port[1]),
        database=dbname,
    )


def generate_signals_sma_crossover(df, fast=20, slow=50):
    df = df.copy()
    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()
    df["signal"] = 0
    df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1
    df.loc[df["sma_fast"] <= df["sma_slow"], "signal"] = -1
    return df["signal"]


def generate_signals_rsi_mean_reversion(df, rsi_period=14, oversold=30, overbought=70):
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(rsi_period).mean()
    loss = (-delta.clip(upper=0)).rolling(rsi_period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    df["signal"] = 0
    df.loc[rsi < oversold, "signal"] = 1
    df.loc[rsi > overbought, "signal"] = -1
    return df["signal"].fillna(0)


def generate_signals_macd_crossover(df):
    df = df.copy()
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    df["signal"] = 0
    df.loc[macd > signal, "signal"] = 1
    df.loc[macd <= signal, "signal"] = -1
    return df["signal"]


def generate_signals_buy_and_hold(df):
    return pd.Series(1, index=df.index)


def generate_signals_vwap_pullback(df, lookback=20, entry_z=0.005, exit_z=0.0):
    df = df.copy()
    df["vwap"] = (df["close"] * df["volume"]).rolling(lookback).sum() / df[
        "volume"
    ].rolling(lookback).sum()
    df["signal"] = 0
    df.loc[df["close"] < df["vwap"] * (1 - entry_z), "signal"] = 1
    df.loc[df["close"] > df["vwap"] * (1 + exit_z), "signal"] = -1
    return df["signal"].fillna(0)


def generate_signals_low_freq_trend(df, fast=50, slow=200):
    df = df.copy()
    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()
    df["signal"] = 0
    df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1
    df.loc[df["sma_fast"] <= df["sma_slow"], "signal"] = -1
    return df["signal"]


async def run_backtest(signals_fn, name, df, symbol):
    signals = signals_fn(df)
    signals = signals.reindex(df.index).fillna(0)
    entry_count = int((signals == 1).sum())
    exit_count = int((signals == -1).sum())

    df = df.copy()
    df["signal"] = signals

    trades = []
    pos = 0
    entry_price = 0.0
    entry_time = None
    entry_bar = 0
    position_series = pd.Series(0, index=df.index, dtype=int)
    closed_positions_count = 0

    for i in range(len(df)):
        sig = signals.iloc[i]
        if pos == 0:
            if sig == 1:
                pos = 1
                entry_price = float(df["close"].iloc[i])
                entry_time = df["time"].iloc[i]
                entry_bar = i
        elif pos == 1:
            if sig == -1:
                exit_price = float(df["close"].iloc[i])
                pnl = exit_price - entry_price
                pnl_pct = pnl / entry_price if entry_price != 0 else 0.0
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": df["time"].iloc[i],
                        "entry_price": round(entry_price, 8),
                        "exit_price": round(exit_price, 8),
                        "side": "long",
                        "pnl": round(pnl, 8),
                        "pnl_pct": round(pnl_pct, 8),
                        "bars_held": i - entry_bar,
                        "exit_reason": "signal",
                    }
                )
                pos = 0
                closed_positions_count += 1
        position_series.iloc[i] = pos

    df["position"] = position_series
    df["market_return"] = df["close"].pct_change().fillna(0)

    n = len(df)
    train_end = int(n * 0.6)
    test_end = int(n * 0.8)
    train_df = df.iloc[:train_end].copy()
    test_df = df.iloc[train_end:test_end].copy()
    holdout_df = df.iloc[test_end:].copy()

    sw_holdout = compute_short_window_metrics(
        holdout_df, holdout_df["position"], holdout_df["market_return"]
    )
    sw_train = compute_short_window_metrics(
        train_df, train_df["position"], train_df["market_return"]
    )
    sw_test = compute_short_window_metrics(
        test_df, test_df["position"], test_df["market_return"]
    )

    composite = compute_composite_short_window_score(sw_holdout)
    cost_ratio = (
        round(sw_holdout["gross_edge"] / sw_holdout["cost_burden"], 2)
        if sw_holdout["cost_burden"] > 0
        else ("N/A" if sw_holdout["gross_edge"] == 0 else "inf")
    )

    tier = (
        "A"
        if composite >= 75
        else "B"
        if composite >= 60
        else "C"
        if composite >= 45
        else "D"
        if composite >= 30
        else "F"
    )

    print(f"\n{'=' * 60}")
    print(f"  CONTROL STRATEGY: {name}")
    print(f"{'=' * 60}")
    print(f"  Symbol:               {symbol}")
    print(f"  Bars:                 {len(df)}  (short-window mode)")
    print(f"  Entry signals:        {entry_count}")
    print(f"  Exit signals:         {exit_count}")
    print(f"  Closed trades (SM):   {closed_positions_count}")
    print(f"  --- HOLDOUT SHORT-WINDOW METRICS ---")
    print(f"  Total return:         {sw_holdout['total_return'] * 100:+.2f}%")
    print(f"  Gross edge:           {sw_holdout['gross_edge'] * 100:+.2f}%")
    print(f"  Cost burden:          {sw_holdout['cost_burden'] * 100:+.2f}%")
    print(f"  Cost efficiency:      {cost_ratio}")
    print(f"  Trades:               {sw_holdout['total_trades']}")
    print(f"  Win rate:             {sw_holdout['win_rate']:.1%}")
    print(f"  Profit factor:        {sw_holdout['profit_factor']:.4f}")
    print(f"  Max drawdown:         {sw_holdout['max_drawdown'] * 100:+.2f}%")
    print(f"  Composite score:      {composite:.1f}")
    print(f"  Tier:                 {tier}")
    print(f"  --- PERIOD COMPARISON ---")
    print(f"  Train return:         {sw_train['total_return'] * 100:+.2f}%")
    print(f"  Test return:          {sw_test['total_return'] * 100:+.2f}%")
    print(f"  Holdout return:       {sw_holdout['total_return'] * 100:+.2f}%")
    print(f"{'=' * 60}\n")

    return {
        "strategy": name,
        "tier": tier,
        "bars": len(df),
        "entry_count": entry_count,
        "exit_count": exit_count,
        "closed_trades": closed_positions_count,
        "total_return_pct": round(sw_holdout["total_return"] * 100, 2),
        "gross_edge_pct": round(sw_holdout["gross_edge"] * 100, 2),
        "cost_burden_pct": round(sw_holdout["cost_burden"] * 100, 2),
        "cost_efficiency_ratio": cost_ratio,
        "trades": sw_holdout["total_trades"],
        "win_rate": sw_holdout["win_rate"],
        "profit_factor": sw_holdout["profit_factor"],
        "max_drawdown_pct": round(sw_holdout["max_drawdown"] * 100, 2),
        "composite_score": composite,
        "train_return": round(sw_train["total_return"] * 100, 2),
        "test_return": round(sw_test["total_return"] * 100, 2),
        "anomaly_exits_per_trade": round(exit_count / closed_positions_count, 2)
        if closed_positions_count > 0
        else "N/A",
    }


async def persist_results(conn, results, symbol, df_start, df_end):
    """Save control strategies and their backtest results to DB"""
    import uuid

    for r in results:
        strat_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO strategies (id, name, code, parameters, status, created_at, author_agent, normalized_strategy)
            VALUES ($1, $2, '', $3, 'benchmark', $4, 'control_benchmark', $3)
            ON CONFLICT DO NOTHING
            """,
            strat_id,
            r["strategy"],
            json.dumps({"control_strategy": r["strategy"], "type": "benchmark"}),
            datetime.utcnow(),
        )
        await conn.execute(
            """
            INSERT INTO backtest_results
                (strategy_id, start_date, end_date, sharpe, cagr, max_drawdown, win_rate,
                 total_trades, passed_validation, results, entry_count, exit_count,
                 bars_processed, short_window_score)
            VALUES ($1, $2, $3, 0, 0, $4, $5, $6, TRUE, $7, $8, $9, $10, $11)
            ON CONFLICT (strategy_id, start_date, end_date) DO UPDATE SET
                short_window_score = EXCLUDED.short_window_score,
                results = EXCLUDED.results
            """,
            strat_id,
            df_start,
            df_end,
            r["max_drawdown_pct"],
            r["win_rate"],
            r["trades"],
            json.dumps(r),
            r["entry_count"],
            r["exit_count"],
            r["bars"],
            r["composite_score"],
        )
    print(f"  Persisted {len(results)} control strategies to database")


async def main():
    conn = await get_connection()
    row = await conn.fetchrow(
        "SELECT symbol, COUNT(*) as cnt FROM market_data_l1 GROUP BY symbol ORDER BY cnt DESC LIMIT 1"
    )
    symbol = row["symbol"]
    print(f"Selected symbol: {symbol} ({row['cnt']} bars)")

    rows = await conn.fetch(
        "SELECT time, open, high, low, close, volume FROM market_data_l1 WHERE symbol = $1 ORDER BY time ASC",
        symbol,
    )
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.astype(
        {"open": float, "high": float, "low": float, "close": float, "volume": float}
    )

    feat_rows = await conn.fetch(
        "SELECT * FROM features_wide WHERE symbol = $1 ORDER BY time ASC", symbol
    )
    if feat_rows:
        cols = feat_rows[0].keys()
        feat_df = pd.DataFrame(feat_rows, columns=cols)
        if "symbol" in feat_df.columns:
            feat_df = feat_df.drop(columns=["symbol"])
        feat_df["time"] = pd.to_datetime(feat_df["time"])
        df = df.merge(feat_df, on="time", how="left")
        df = df.sort_values("time").ffill().bfill()

    print(
        f"Data shape: {df.shape}, range: {df['time'].iloc[0]} -> {df['time'].iloc[-1]}"
    )
    print()

    controls = [
        (
            "SMA Crossover (20/50)",
            lambda df: generate_signals_sma_crossover(df, 20, 50),
        ),
        (
            "SMA Crossover (10/30)",
            lambda df: generate_signals_sma_crossover(df, 10, 30),
        ),
        ("RSI Mean Reversion", generate_signals_rsi_mean_reversion),
        ("MACD Crossover", generate_signals_macd_crossover),
        ("Buy & Hold", generate_signals_buy_and_hold),
        ("VWAP Pullback", generate_signals_vwap_pullback),
        ("Low-Freq Trend (50/200)", generate_signals_low_freq_trend),
    ]

    results = []
    for name, fn in controls:
        results.append(await run_backtest(fn, name, df, symbol))

    # Persist to DB
    await persist_results(
        conn, results, symbol, df["time"].iloc[0], df["time"].iloc[-1]
    )
    await conn.close()

    # Summary table
    print()
    print("=" * 100)
    print("  CONTROL STRATEGY BENCHMARK (SHORT-WINDOW MODE)")
    print("=" * 100)
    header = (
        f"  {'Strategy':>28} {'Tier':>4} {'Comp':>6} {'Ret%':>8} {'Gross':>7} "
        f"{'Cost':>7} {'CostEff':>7} {'Trades':>6} {'PF':>5} {'WR':>5} {'DD%':>7}"
    )
    print(header)
    print("  " + "-" * 96)
    for r in results:
        ce = (
            str(r["cost_efficiency_ratio"])[:7]
            if isinstance(r["cost_efficiency_ratio"], str)
            else f"{r['cost_efficiency_ratio']:>7.2f}"
        )
        print(
            f"  [{r['tier']}] {r['strategy']:>24}  {r['composite_score']:>5.1f}  "
            f"{r['total_return_pct']:>+7.2f}  {r['gross_edge_pct']:>+6.2f}  "
            f"{r['cost_burden_pct']:>+6.2f}  {ce:>7}  {r['trades']:>4}  "
            f"{r['profit_factor']:>4.2f}  {r['win_rate']:>4.0%}  {r['max_drawdown_pct']:>+6.2f}"
        )
    print("=" * 100)

    # Phase C — Score distribution interpretation
    print()
    print("--- TIER DISTRIBUTION ---")
    tiers = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for r in results:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    for t in ["A", "B", "C", "D", "F"]:
        if tiers[t] > 0:
            print(f"  Tier {t}: {tiers[t]} strategies")
    avg_score = np.mean([r["composite_score"] for r in results])
    print(f"  Average composite: {avg_score:.1f}")

    # Sanity checks
    print()
    print("--- SANITY CHECKS ---")
    issues = []

    # Rule 1: SMA 20/50 should generally outperform overactive MACD if costs dominate
    sma_20 = next(r for r in results if r["strategy"] == "SMA Crossover (20/50)")
    macd = next(r for r in results if r["strategy"] == "MACD Crossover")
    bh = next(r for r in results if r["strategy"] == "Buy & Hold")
    vwap = next(r for r in results if r["strategy"] == "VWAP Pullback")
    lf = next(r for r in results if r["strategy"] == "Low-Freq Trend (50/200)")

    if macd["cost_burden_pct"] > sma_20["cost_burden_pct"]:
        print(
            f"  [OK] MACD cost ({macd['cost_burden_pct']}%) > SMA20/50 cost ({sma_20['cost_burden_pct']}%) — higher turnover expected"
        )
    else:
        issues.append("MACD cost not higher than SMA — unexpected")

    if bh["cost_burden_pct"] <= 0.01:
        print(
            f"  [OK] Buy & Hold cost ({bh['cost_burden_pct']}%) — near-zero as expected"
        )
    else:
        issues.append(f"Buy & Hold cost ({bh['cost_burden_pct']}%) should be near-zero")

    if lf["trades"] <= sma_20["trades"]:
        print(
            f"  [OK] Low-freq trades ({lf['trades']}) <= SMA20/50 trades ({sma_20['trades']}) — lower frequency expected"
        )
    else:
        issues.append("Low-freq should have fewer trades than SMA20/50")

    # Rule 2: Buy & Hold should not be absurdly ranked
    min_score = min(r["composite_score"] for r in results)
    if bh["composite_score"] > min_score:
        print(
            f"  [OK] Buy & Hold ({bh['composite_score']}) not the lowest ranked strategy"
        )
    else:
        issues.append("Buy & Hold is lowest ranked — may indicate data or cost issue")

    # Rule 4: Check for anomaly exits per trade across all strategies
    high_anomaly = [
        r
        for r in results
        if isinstance(r["anomaly_exits_per_trade"], (int, float))
        and r["anomaly_exits_per_trade"] > 10
    ]
    if high_anomaly:
        print(
            f"  [WARN] {len(high_anomaly)} strategies have high exit/entry anomaly: {', '.join(r['strategy'] for r in high_anomaly)}"
        )
    else:
        print(f"  [OK] No anomalous exit/entry ratios detected")

    print()
    if issues:
        print("--- ISSUES FOUND ---")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("--- ALL SANITY CHECKS PASSED ---")

    # Phase D — Cost model insight
    print()
    print("--- COST MODEL INSIGHT ---")
    print(f"  {'Strategy':>28} {'Gross%':>8} {'Cost%':>8} {'CostEff':>8} {'Trades':>6}")
    print(f"  {'-' * 58}")
    sorted_by_cost = sorted(results, key=lambda r: r["cost_burden_pct"], reverse=True)
    for r in sorted_by_cost:
        ce = (
            str(r["cost_efficiency_ratio"])[:8]
            if isinstance(r["cost_efficiency_ratio"], str)
            else f"{r['cost_efficiency_ratio']:>8.2f}"
        )
        print(
            f"  {r['strategy']:>28} {r['gross_edge_pct']:>+7.2f} {r['cost_burden_pct']:>+7.2f} {ce:>8} {r['trades']:>4}"
        )
    print()

    passed_50 = [r for r in results if r["composite_score"] >= 50]
    passed_45 = [r for r in results if r["composite_score"] >= 45]
    if passed_50:
        print(
            f"OK - {len(passed_50)}/{len(results)} strategies score >= 50 (old tier threshold)"
        )
        print(
            f"     {len(passed_45)}/{len(results)} strategies score >= 45 (suggested tier threshold)"
        )
        print(
            f"     Controls ranked sensibly. Engine is sound with short-window metrics."
        )
    elif passed_45:
        print(f"WARN - No strategies >= 50, but {len(passed_45)}/{len(results)} >= 45")
        print(
            f"       Suggested tier threshold (45) may be appropriate for short-window mode."
        )
    else:
        print(f"ISSUE - All strategies < 45. Review cost model or data quality.")


if __name__ == "__main__":
    asyncio.run(main())
