#!/usr/bin/env python3
"""
Validation script for paper trading performance system.

Computes metrics for all strategies with paper_trades, produces
top-20 rankings by monthly return, Sharpe, and profit factor,
and lists strategies exceeding 20% monthly return.

Usage:
    python scripts/validate_paper_performance.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas.data.storage.timescale_client import TimescaleClient
from atlas.analytics.paper_performance import PaperPerformanceMetrics


async def main():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/atlas",
    )
    db = TimescaleClient(db_url)
    await db.connect()
    perf = PaperPerformanceMetrics(db)

    print("=" * 80)
    print("PAPER TRADING PERFORMANCE VALIDATION")
    print("=" * 80)

    # Compute metrics for all strategies
    print("\n[1] Computing metrics for all strategies with paper_trades...")
    results = await perf.compute_all()
    print(f"    Computed metrics for {len(results)} strategies\n")

    # Top 20 by monthly return
    print("[2] Top 20 by Monthly Return %")
    print("-" * 80)
    ranked = await perf.get_ranked(sort_by="monthly_return_pct", limit=20)
    print(
        f"{'Rank':<5} {'Strategy':<30} {'Mo Return':<12} {'Sharpe':<10} {'PF':<10} {'WinRate':<10} {'Trades':<8} {'Qualified':<10}"
    )
    print("-" * 80)
    for i, r in enumerate(ranked, 1):
        q = "PASS" if r["is_qualified"] else "--"
        print(
            f"{i:<5} {r['name'][:28]:<30} {r['monthly_return_pct']:>8.2f}%  {r['sharpe_ratio']:>8.2f}  {r['profit_factor']:>8.2f}  {r['win_rate'] * 100:>7.1f}%  {r['total_trades']:>5}  {q:<10}"
        )

    # Top 10 by Sharpe
    print("\n[3] Top 10 by Sharpe Ratio")
    print("-" * 60)
    ranked_sharpe = await perf.get_ranked(sort_by="sharpe_ratio", limit=10)
    print(
        f"{'Rank':<5} {'Strategy':<30} {'Sharpe':<12} {'Mo Return':<12} {'Qualified':<10}"
    )
    print("-" * 60)
    for i, r in enumerate(ranked_sharpe, 1):
        q = "PASS" if r["is_qualified"] else "--"
        print(
            f"{i:<5} {r['name'][:28]:<30} {r['sharpe_ratio']:>8.2f}     {r['monthly_return_pct']:>8.2f}%  {q:<10}"
        )

    # Top 10 by Profit Factor
    print("\n[4] Top 10 by Profit Factor")
    print("-" * 60)
    ranked_pf = await perf.get_ranked(sort_by="profit_factor", limit=10)
    print(
        f"{'Rank':<5} {'Strategy':<30} {'PF':<12} {'Mo Return':<12} {'Qualified':<10}"
    )
    print("-" * 60)
    for i, r in enumerate(ranked_pf, 1):
        q = "PASS" if r["is_qualified"] else "--"
        print(
            f"{i:<5} {r['name'][:28]:<30} {r['profit_factor']:>8.2f}     {r['monthly_return_pct']:>8.2f}%  {q:<10}"
        )

    # Strategies above 20% monthly return
    print("\n[5] Strategies exceeding 20% monthly return")
    print("-" * 60)
    above_20 = [r for r in ranked if r["monthly_return_pct"] >= 20]
    if above_20:
        for r in above_20:
            q = "PASS" if r["is_qualified"] else "--"
            print(
                f"  {r['name']:<30} {r['monthly_return_pct']:>8.2f}%  Sharpe={r['sharpe_ratio']:.2f}  PF={r['profit_factor']:.2f}  Trades={r['total_trades']}  {q}"
            )
    else:
        print("  None found")

    # Qualified strategies
    print("\n[6] Strategies qualified for promotion")
    print("-" * 60)
    qualified = [r for r in ranked if r["is_qualified"]]
    if qualified:
        for r in qualified:
            print(
                f"  {r['name']:<30} MoRet={r['monthly_return_pct']:.2f}%  Sharpe={r['sharpe_ratio']:.2f}  PF={r['profit_factor']:.2f}  DD={r['max_drawdown_pct']:.2f}%  Trades={r['total_trades']}"
            )
    else:
        print("  None found (expected until all 5 criteria are met)")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
