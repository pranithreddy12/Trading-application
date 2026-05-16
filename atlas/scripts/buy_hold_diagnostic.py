"""
Diagnostic: Buy-and-hold benchmark + holdout period analysis
"""

import asyncio
import asyncpg
import numpy as np
import pandas as pd
import os, sys

sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf8", buffering=1)


async def main():
    conn = await asyncpg.connect(
        user="postgres",
        password="password",
        host="localhost",
        port=5433,
        database="atlas",
    )

    row = await conn.fetchrow(
        "SELECT symbol, COUNT(*) as cnt FROM market_data_l1 GROUP BY symbol ORDER BY cnt DESC LIMIT 1"
    )
    symbol = row["symbol"]
    print(f"Symbol: {symbol}, Bars: {row['cnt']}")

    rows = await conn.fetch(
        """
        SELECT time, open, high, low, close, volume
        FROM market_data_l1 WHERE symbol = $1 ORDER BY time ASC
    """,
        symbol,
    )
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"])

    n = len(df)
    train_end = int(n * 0.6)
    test_end = int(n * 0.8)

    # Print time ranges
    print(f"\nFull period:  {df['time'].iloc[0]} → {df['time'].iloc[-1]}  ({n} bars)")
    print(
        f"Train:        {df['time'].iloc[0]} → {df['time'].iloc[train_end]}  ({train_end} bars)"
    )
    print(
        f"Test:         {df['time'].iloc[train_end]} → {df['time'].iloc[test_end]}  ({test_end - train_end} bars)"
    )
    print(
        f"Holdout:      {df['time'].iloc[test_end]} → {df['time'].iloc[-1]}  ({n - test_end} bars)"
    )

    # Buy-and-hold for each period
    for name, sub_df in [
        ("Full", df),
        ("Train", df.iloc[:train_end]),
        ("Test", df.iloc[train_end:test_end]),
        ("Holdout", df.iloc[test_end:]),
    ]:
        start_px = sub_df["close"].iloc[0]
        end_px = sub_df["close"].iloc[-1]
        ret = (end_px / start_px) - 1
        print(f"\n  {name:>8}: ${start_px:.2f} → ${end_px:.2f}  Return={ret:+.4%}")

    # Check first/last 10 prices
    print(f"\nFirst 10 closes: {df['close'].iloc[:10].tolist()}")
    print(f"Last 10 closes:  {df['close'].iloc[-10:].tolist()}")

    # Direction counts
    changes = df["close"].pct_change().fillna(0)
    up = (changes > 0).sum()
    dn = (changes < 0).sum()
    print(f"\nUp bars: {up}, Down bars: {dn}, Flat: {n - up - dn}")

    # Check RSI from features_wide
    feat_rows = await conn.fetch(
        """
        SELECT time, rsi_14 FROM features_wide WHERE symbol = $1 ORDER BY time ASC
    """,
        symbol,
    )
    if feat_rows:
        rsi_vals = [r["rsi_14"] for r in feat_rows if r["rsi_14"] is not None]
        print(f"\nRSI(14) samples from features_wide:")
        print(f"  Non-null: {len(rsi_vals)}/{len(feat_rows)}")
        print(
            f"  Min: {min(rsi_vals):.4f}, Max: {max(rsi_vals):.4f}, Mean: {np.mean(rsi_vals):.4f}"
        )
        print(f"  First 20: {[round(v, 2) for v in rsi_vals[:20]]}")
        print(f"  Last 20:  {[round(v, 2) for v in rsi_vals[-20:]]}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
