"""
Run walk-forward validation on top 20 validated strategies.
Satisfies VAL-004 requirement.
"""
import asyncio
import json
import numpy as np
import pandas as pd
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_validation.walk_forward_analyzer import WalkForwardAnalyzer


async def main():
    print("=== WALK-FORWARD VALIDATION START ===", flush=True)

    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis_client = Redis.from_url(settings.redis_url)

    wf = WalkForwardAnalyzer(
        redis_client=redis_client,
        db_client=db,
        n_windows=5,
        train_pct=0.7,
        min_trades_per_window=2,
    )

    # Fetch top 20 validated strategies
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT s.id, s.name, s.code, b.sharpe, b.total_trades
                FROM strategies s
                JOIN backtest_results b ON b.strategy_id = s.id
                WHERE s.status IN ('validated', 'research_candidate')
                  AND s.code IS NOT NULL
                  AND LENGTH(s.code) > 50
                ORDER BY b.sharpe DESC NULLS LAST
                LIMIT 20
            """)
        )
        strategies = result.fetchall()

    print(f"Found {len(strategies)} strategies to walk-forward validate", flush=True)

    # Fetch market data (use the symbol with most data)
    async with db.engine.connect() as conn:
        sym_result = await conn.execute(
            text("""
                SELECT symbol, COUNT(*) as bars
                FROM market_data_l1
                GROUP BY symbol
                ORDER BY bars DESC
                LIMIT 1
            """)
        )
        sym_row = sym_result.fetchone()
        symbol = sym_row[0]
        bar_count = sym_row[1]
        print(f"Using symbol {symbol} ({bar_count} bars)", flush=True)

    # Load market data
    async with db.engine.connect() as conn:
        md_result = await conn.execute(
            text("""
                SELECT time, open, high, low, close, volume
                FROM market_data_l1
                WHERE symbol = :symbol
                ORDER BY time ASC
            """),
            {"symbol": symbol},
        )
        rows = md_result.fetchall()

    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

    # Load features
    async with db.engine.connect() as conn:
        feat_result = await conn.execute(
            text("""
                SELECT time, feature_name, value
                FROM features
                WHERE symbol = :symbol
                ORDER BY time ASC
            """),
            {"symbol": symbol},
        )
        feat_rows = feat_result.fetchall()

    if feat_rows:
        feat_df = pd.DataFrame(feat_rows, columns=["time", "feature_name", "value"])
        feat_df["time"] = pd.to_datetime(feat_df["time"])
        feat_pivot = feat_df.pivot_table(
            index="time", columns="feature_name", values="value", aggfunc="first"
        ).reset_index()
        feat_pivot.columns.name = None
        feat_pivot.columns = [str(c) for c in feat_pivot.columns]
        df = df.merge(feat_pivot, on="time", how="left")
        df = df.sort_values("time").ffill().bfill()

    print(f"DataFrame: {len(df)} rows, {len(df.columns)} columns", flush=True)

    results_summary = []

    for i, strat in enumerate(strategies):
        sid = str(strat[0])
        name = strat[1]
        code = strat[2]
        sharpe = strat[3]

        print(f"\n[{i+1}/20] {name} (sharpe={float(sharpe):.1f})", flush=True)

        try:
            namespace = {"pd": pd, "np": np}
            exec(code, namespace)

            strategy_instance = None
            for obj_name, obj in namespace.items():
                if isinstance(obj, type) and callable(getattr(obj, "generate_signals", None)):
                    strategy_instance = obj()
                    break

            if not strategy_instance:
                print(f"  SKIP: No strategy class found", flush=True)
                continue

            signals = strategy_instance.generate_signals(df)
            if not isinstance(signals, pd.Series):
                print(f"  SKIP: signals not a Series", flush=True)
                continue

            signals = signals.reindex(df.index).fillna(0)
            entry_count = int((signals == 1).sum())
            print(f"  Entries: {entry_count}", flush=True)

            if entry_count < 5:
                print(f"  SKIP: too few entries", flush=True)
                continue

            wf_result = await wf.analyze(
                strategy_id=sid,
                df=df,
                signals=signals,
                background_results={},
            )

            wf_score = wf_result["walk_forward_score"]
            tc = wf_result["temporal_consistency"]
            regime = wf_result["regime_survival_score"]
            survived = wf_result["n_windows_survived"]
            total = wf_result["n_windows_total"]

            print(
                f"  WF Score: {wf_score:.2f} | Temporal: {tc:.2f} | "
                f"Regime: {regime:.2f} | Windows: {survived}/{total}",
                flush=True,
            )

            results_summary.append({
                "name": name,
                "strategy_id": sid,
                "wf_score": wf_score,
                "temporal_consistency": tc,
                "regime_survival": regime,
                "windows_survived": survived,
                "windows_total": total,
            })

        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            continue

    print("\n=== WALK-FORWARD RESULTS SUMMARY ===", flush=True)
    print(f"{'Name':<50} {'WF Score':>8} {'Temporal':>8} {'Windows':>8}", flush=True)
    print("-" * 78, flush=True)

    passed = 0
    for r in sorted(results_summary, key=lambda x: x["wf_score"], reverse=True):
        status = "PASS" if r["wf_score"] >= 0.4 else "FAIL"
        print(
            f"{r['name']:<50} {r['wf_score']:>8.2f} {r['temporal_consistency']:>8.2f} "
            f"{r['windows_survived']}/{r['windows_total']:>3} {status}",
            flush=True,
        )
        if r["wf_score"] >= 0.4:
            passed += 1

    print(f"\nTotal passed walk-forward (≥40% windows): {passed}/{len(results_summary)}", flush=True)
    print("=== WALK-FORWARD VALIDATION COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
