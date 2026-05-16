"""
Temporal Governance Validation Harness — Priority 5
Asks: "Is this strategy STILL good recently?" not "Was it good historically?"
Compares fresh short_window_score on recent data vs stored historical score.
"""

import asyncio
import sys
import json
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import text

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.short_window_evaluator import (
    compute_short_window_metrics,
    compute_composite_short_window_score,
)


# ---------------------------------------------------------------------------
# Governance thresholds
# ---------------------------------------------------------------------------
HEALTHY_RATIO = 0.80  # fresh score >= 80% of historical → HEALTHY
DECAYING_RATIO = 0.60  # fresh score >= 60% but < 80% → DECAYING
MIN_RECENT_BARS = 100  # need at least this many bars for a meaningful check
STALE_SCORE_FLOOR = 30.0  # fresh score below this → FAILED regardless

GOV_STATUS_HEALTHY = "HEALTHY"
GOV_STATUS_DECAYING = "DECAYING"
GOV_STATUS_STALE = "STALE"
GOV_STATUS_FAILED = "FAILED"
GOV_STATUS_SKIP = "SKIP"
GOV_STATUS_ERROR = "ERROR"


def assess_governance(historical_score: float, fresh_score: float) -> str:
    if fresh_score < STALE_SCORE_FLOOR:
        return GOV_STATUS_FAILED
    if historical_score <= 0:
        return GOV_STATUS_SKIP
    ratio = fresh_score / historical_score
    if ratio >= HEALTHY_RATIO:
        return GOV_STATUS_HEALTHY
    if ratio >= DECAYING_RATIO:
        return GOV_STATUS_DECAYING
    return GOV_STATUS_STALE


async def load_recent_data(
    db: TimescaleClient, symbol: str, recent_bars: int
) -> pd.DataFrame:
    """Load most recent market_data_l1 + features_wide for governance."""
    async with db.engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT time, open, high, low, close, volume
                FROM market_data_l1
                WHERE symbol = :symbol
                ORDER BY time DESC
                LIMIT :limit
                """
            ),
            {"symbol": symbol, "limit": recent_bars},
        )
        records = rows.fetchall()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(
            records, columns=["time", "open", "high", "low", "close", "volume"]
        )
        df = df.sort_values("time").reset_index(drop=True)
        df["time"] = pd.to_datetime(df["time"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        feat_rows = await conn.execute(
            text(
                """
                SELECT * FROM features_wide
                WHERE symbol = :symbol
                ORDER BY time DESC
                LIMIT :limit
                """
            ),
            {"symbol": symbol, "limit": recent_bars},
        )
        feat_records = feat_rows.fetchall()
        if feat_records:
            cols = feat_rows.keys()
            feat_df = pd.DataFrame(feat_records, columns=cols)
            if "symbol" in feat_df.columns:
                feat_df = feat_df.drop(columns=["symbol"])
            feat_df["time"] = pd.to_datetime(feat_df["time"])
            df = df.merge(feat_df, on="time", how="left")
            df = df.sort_values("time").ffill().bfill()
    return df


def run_state_machine(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Run state machine on df with 'signal' column, return (df_with_position, trades)."""
    trades = []
    pos = 0
    entry_price = 0.0
    entry_bar = 0
    position_series = pd.Series(0, index=df.index, dtype=int)

    for i in range(len(df)):
        sig = df["signal"].iloc[i]
        if pos == 0:
            if sig == 1:
                pos = 1
                entry_price = float(df["close"].iloc[i])
                entry_bar = i
        elif pos == 1:
            if sig == -1:
                exit_price = float(df["close"].iloc[i])
                pnl = exit_price - entry_price
                pnl_pct = pnl / entry_price if entry_price != 0 else 0.0
                trades.append(
                    {
                        "entry_time": df["time"].iloc[entry_bar],
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
        position_series.iloc[i] = pos

    df = df.copy()
    df["position"] = position_series
    df["market_return"] = df["close"].pct_change().fillna(0)
    return df, trades


async def evaluate_strategy_on_recent_data(
    db: TimescaleClient,
    strategy_id: str,
    name: str,
    code: str,
    parameters: dict,
    df: pd.DataFrame,
) -> dict | None:
    """Exec strategy code on recent df, compute fresh short_window_score. Returns result dict or None."""
    if len(df) < MIN_RECENT_BARS:
        logger.warning(f"{name}: insufficient data ({len(df)} < {MIN_RECENT_BARS})")
        return None

    # Try to exec the strategy code
    if not code or not code.strip():
        logger.warning(f"{name}: no executable code, skipping")
        return None

    strategy_instance = None
    try:
        namespace = {"pd": pd, "np": np}
        exec(code, namespace)
        for _name, obj in namespace.items():
            if isinstance(obj, type) and callable(
                getattr(obj, "generate_signals", None)
            ):
                strategy_instance = obj()
                break
    except Exception as e:
        logger.warning(f"{name}: code exec failed: {e}")
        return None

    if strategy_instance is None:
        logger.warning(f"{name}: no class with generate_signals found")
        return None

    # Generate signals on recent data
    try:
        signals = strategy_instance.generate_signals(df)
    except Exception as e:
        logger.warning(f"{name}: generate_signals failed on recent data: {e}")
        return None

    if not isinstance(signals, pd.Series):
        logger.warning(
            f"{name}: generate_signals returned {type(signals)}, expected Series"
        )
        return None

    signals = signals.reindex(df.index).fillna(0)
    df["signal"] = signals

    # Run state machine
    df, trades = run_state_machine(df)

    # Compute short-window metrics on the entire recent window
    sw = compute_short_window_metrics(
        df,
        df["position"],
        df["market_return"],
        position_size=0.10,
        commission_pct=0.001,
        slippage_pct=0.0005,
        spread_cost_pct=0.0005,
    )
    fresh_score = compute_composite_short_window_score(sw)

    return {
        "strategy_id": strategy_id,
        "name": name,
        "fresh_score": round(float(fresh_score), 1),
        "total_return_pct": round(float(sw["total_return"] * 100), 2),
        "gross_edge_pct": round(float(sw["gross_edge"] * 100), 2),
        "cost_burden_pct": round(float(sw["cost_burden"] * 100), 2),
        "trades": int(sw["total_trades"]),
        "win_rate": float(sw["win_rate"]),
        "profit_factor": float(sw["profit_factor"]),
        "max_drawdown_pct": round(float(sw["max_drawdown"] * 100), 2),
        "bars_used": len(df),
        "closed_trades": len(trades),
    }


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()

    import argparse

    parser = argparse.ArgumentParser(description="Temporal Governance Check")
    parser.add_argument("--strategy-id", help="Check a single strategy by ID")
    parser.add_argument(
        "--limit", type=int, default=10, help="Max strategies to check (default 10)"
    )
    parser.add_argument(
        "--recent-bars",
        type=int,
        default=300,
        help="Recent bars for evaluation (default 300)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Healthy decay ratio (default 0.80)",
    )
    parser.add_argument("--symbol", help="Symbol to check (default: most data)")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    # Pick symbol
    if args.symbol:
        symbol = args.symbol
    else:
        async with db.engine.connect() as conn:
            row = await conn.execute(
                text(
                    "SELECT symbol FROM market_data_l1 GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 1"
                )
            )
            symbol = row.fetchone()[0]

    logger.info(f"Governance check: symbol={symbol}, recent_bars={args.recent_bars}")

    # Load recent data
    df = await load_recent_data(db, symbol, args.recent_bars)
    if df.empty:
        print(f"ERROR: No data for {symbol}")
        return 1

    logger.info(f"Loaded {len(df)} recent bars for {symbol}")

    # Query strategies
    if args.strategy_id:
        async with db.engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT s.id, s.name, s.code, s.parameters, s.status,
                           b.short_window_score
                    FROM strategies s
                    JOIN backtest_results b ON s.id = b.strategy_id
                    WHERE s.id = :sid AND b.short_window_score IS NOT NULL
                    """
                ),
                {"sid": args.strategy_id},
            )
            strategies = [dict(r._mapping) for r in rows.fetchall()]
    else:
        async with db.engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT s.id, s.name, s.code, s.parameters, s.status,
                           b.short_window_score
                    FROM strategies s
                    JOIN backtest_results b ON s.id = b.strategy_id
                    WHERE b.short_window_score IS NOT NULL
                      AND s.status IN ('pending_validation', 'benchmark')
                    ORDER BY b.short_window_score DESC
                    LIMIT :limit
                    """
                ),
                {"limit": args.limit},
            )
            strategies = [dict(r._mapping) for r in rows.fetchall()]

    if not strategies:
        print("No strategies found with short_window_score.")
        return 0

    logger.info(f"Checking {len(strategies)} strategies for temporal governance")

    results = []
    for s in strategies:
        sid = str(s["id"])
        name = s["name"]
        historical_score = (
            float(s["short_window_score"]) if s["short_window_score"] else 0.0
        )
        code = s.get("code", "") or ""
        params_raw = s.get("parameters", {})
        parameters = params_raw if isinstance(params_raw, dict) else {}

        eval_result = await evaluate_strategy_on_recent_data(
            db, sid, name, code, parameters, df
        )

        if eval_result is None:
            results.append(
                {
                    "strategy_id": sid,
                    "name": name,
                    "historical_score": historical_score,
                    "fresh_score": None,
                    "gov_status": GOV_STATUS_ERROR,
                    "reason": "eval_failed",
                }
            )
            continue

        fresh_score = eval_result["fresh_score"]
        gov_status = assess_governance(historical_score, fresh_score)
        eval_result["historical_score"] = historical_score
        eval_result["gov_status"] = gov_status
        results.append(eval_result)

    # Output
    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return 0

    print()
    print("=" * 120)
    print("  TEMPORAL GOVERNANCE CHECK")
    print("=" * 120)
    header = (
        f"  {'Status':>8} {'Chg':>8} {'Hist':>6} {'Fresh':>6} "
        f"{'Ret%':>7} {'Gross%':>7} {'Cost%':>7} {'Trades':>5} "
        f"{'WR':>4} {'PF':>5} {'Strategy':>30}"
    )
    print(header)
    print("  " + "-" * 112)

    healthy = decaying = stale = failed = error = 0
    for r in results:
        hs = r["historical_score"]
        fs = r.get("fresh_score")
        if fs is not None:
            delta = fs - hs
            delta_str = f"{delta:+.1f}"
            status = r["gov_status"]
        else:
            delta_str = "N/A"
            status = GOV_STATUS_ERROR

        if status == GOV_STATUS_HEALTHY:
            healthy += 1
        elif status == GOV_STATUS_DECAYING:
            decaying += 1
        elif status == GOV_STATUS_STALE:
            stale += 1
        elif status == GOV_STATUS_FAILED:
            failed += 1
        else:
            error += 1

        def _s(v, fmt, width):
            if isinstance(v, str):
                return "N/A".rjust(width)
            try:
                return f"{v:{fmt}}".rjust(width)
            except (ValueError, TypeError):
                return "N/A".rjust(width)

        name = r["name"][:30]
        ret_s = _s(r.get("total_return_pct"), "+.2f", 7)
        gross_s = _s(r.get("gross_edge_pct"), "+.2f", 7)
        cost_s = _s(r.get("cost_burden_pct"), "+.2f", 7)
        winrate = r.get("win_rate")
        wr_s = (
            _s(winrate, ".0%", 4) if isinstance(winrate, float) else _s(winrate, "", 4)
        )
        profitf = r.get("profit_factor")
        pf_s = (
            _s(profitf, ".2f", 5) if isinstance(profitf, float) else _s(profitf, "", 5)
        )
        t = r.get("trades")
        trades_s = str(t).rjust(4) if isinstance(t, int) else "N/A".rjust(4)

        fs_str = f"{fs:>6.1f}" if fs is not None else "  N/A"
        print(
            f"  [{status:>7}] {delta_str:>8} {hs:>6.1f} {fs_str} "
            f"{ret_s} {gross_s} {cost_s} {trades_s} "
            f"{wr_s} {pf_s} {name:>30}"
        )

    print("=" * 120)
    print()
    print("--- GOVERNANCE SUMMARY ---")
    print(f"  HEALTHY:  {healthy}")
    print(f"  DECAYING: {decaying}")
    print(f"  STALE:    {stale}")
    print(f"  FAILED:   {failed}")
    print(f"  ERROR:    {error}")
    total_checked = healthy + decaying + stale + failed
    if total_checked > 0:
        print(
            f"  Pass rate (HEALTHY / total): {healthy}/{total_checked} ({healthy / total_checked:.0%})"
        )
    print()

    # Failure breakdown
    if any(r["gov_status"] != GOV_STATUS_HEALTHY for r in results):
        print("--- DECAY / FAILURE BREAKDOWN ---")
        for r in results:
            if r["gov_status"] == GOV_STATUS_HEALTHY:
                continue
            fs = r.get("fresh_score")
            hs = r["historical_score"]
            ratio = f"{fs / hs:.0%}" if fs and hs > 0 else "N/A"
            print(
                f"  [{r['gov_status']}] {r['name']:>30}  hist={hs:.1f}  fresh={fs}  ratio={ratio}"
            )
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
