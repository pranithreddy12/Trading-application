"""
ALPHA REBUILD P1 — canonical single-source metric derivation from the trade ledger.
SHADOW ONLY: reads backtest_trades, writes nothing to production paths.

compute_ledger_metrics(trades) is the proposed single source of truth. This script
also reconciles it against currently-stored backtest_results (Path A sharpe / Path B
rest) to quantify the migration delta.

Canonical conventions (system's own constants):
  ROUNDTRIP cost = 0.004 ; position_size = 0.10 ; units = fractions ; per-trade win/PF.
"""
import asyncio, os, re, math, statistics as st
import asyncpg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDTRIP = 0.004
SIZE = 0.10

def dsn():
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            if line.strip().startswith("DATABASE_URL="):
                return re.sub(r"\+asyncpg", "", line.split("=", 1)[1].strip())

def clip(x, lo, hi): return max(lo, min(hi, x))

def compute_ledger_metrics(trades: list[dict]) -> dict:
    """trades: [{pnl_pct, bars_held, entry_time, exit_time}, ...] (chronological)."""
    N = len(trades)
    if N == 0:
        return {"n_trades": 0}
    tr = sorted(trades, key=lambda t: t["entry_time"])
    # per-trade net & gross scaled returns
    r = [(float(t["pnl_pct"]) - ROUNDTRIP) * SIZE for t in tr]
    g = [float(t["pnl_pct"]) * SIZE for t in tr]
    # equity curves (trade-sequenced)
    eq, e = [], 1.0
    for x in r:
        e *= (1.0 + x); eq.append(e)
    total_return = eq[-1] - 1.0
    geq, ge = 1.0, 1.0
    for x in g:
        ge *= (1.0 + x)
    gross_edge = ge - 1.0
    cost_burden = gross_edge - total_return
    # drawdown (fraction, clipped >= -1)
    peak, mdd = -1e9, 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    mdd = clip(mdd, -1.0, 0.0)
    # per-trade win/PF/expectancy (NET)
    wins = [x for x in r if x > 0]; losses = [x for x in r if x < 0]
    win_rate = len(wins) / N
    pf = (sum(wins) / abs(sum(losses))) if losses else (5.0 if wins else 0.0)
    pf = min(pf, 5.0)
    expectancy = sum(r) / N
    # annualization from trade-time span
    span_days = max((tr[-1]["exit_time"] - tr[0]["entry_time"]).total_seconds() / 86400.0, 0.5)
    tpy = N * 365.0 / span_days
    mu, sd = st.mean(r), (st.pstdev(r) if N > 1 else 0.0)
    sharpe = clip((mu / sd) * math.sqrt(tpy), -10, 10) if sd > 1e-12 else 0.0
    dr = [x for x in r if x < 0]
    dsd = st.pstdev(dr) if len(dr) > 1 else 0.0
    sortino = clip((mu / dsd) * math.sqrt(tpy), -10, 10) if dsd > 1e-12 else 0.0
    calmar = (total_return / abs(mdd)) if mdd < 0 else 0.0
    avg_dur = sum(t["bars_held"] for t in tr) / N
    return dict(n_trades=N, total_return=total_return, gross_edge=gross_edge,
                cost_burden=cost_burden, max_drawdown=mdd, win_rate=win_rate,
                profit_factor=pf, expectancy=expectancy, sharpe=sharpe,
                sortino=sortino, calmar=calmar, avg_trade_duration_bars=avg_dur)

def desc(v):
    v=[x for x in v if x is not None]
    if not v: return "n/a"
    s=sorted(v); n=len(s); p=lambda q:s[min(n-1,int(q*n))]
    return f"min={s[0]:.4g} p25={p(.25):.4g} med={s[n//2]:.4g} mean={sum(s)/n:.4g} p75={p(.75):.4g} max={s[-1]:.4g}"

async def main():
    c = await asyncpg.connect(dsn())
    rows = await c.fetch("SELECT strategy_id, pnl_pct, bars_held, entry_time, exit_time FROM backtest_trades")
    by = {}
    for r in rows:
        by.setdefault(str(r["strategy_id"]), []).append(dict(pnl_pct=r["pnl_pct"], bars_held=r["bars_held"], entry_time=r["entry_time"], exit_time=r["exit_time"]))
    stored = {str(r["strategy_id"]): r for r in await c.fetch("SELECT DISTINCT ON (strategy_id) strategy_id, sharpe, win_rate, max_drawdown, total_trades, results FROM backtest_results ORDER BY strategy_id, end_date DESC")}
    import json
    def stot(r):
        j=r["results"];
        if isinstance(j,str):
            try: j=json.loads(j)
            except: j={}
        return (j or {}).get("total_return")

    uni = {sid: compute_ledger_metrics(tr) for sid, tr in by.items() if len(tr) >= 2}
    print(f"=== CANONICAL LEDGER METRICS — {len(uni)} strategies (>=2 trades) ===")
    for k in ("n_trades","total_return","gross_edge","cost_burden","max_drawdown","win_rate","profit_factor","expectancy","sharpe","sortino","calmar","avg_trade_duration_bars"):
        print(f"  {k:24} {desc([m[k] for m in uni.values() if k in m])}")

    # reconciliation vs stored
    print("\n=== RECONCILIATION: canonical (ledger) vs stored (Path A/B) ===")
    common = [s for s in uni if s in stored]
    print(f"  strategies with both: {len(common)}")
    # sharpe: stored Path A (inflated) vs canonical
    print(f"  SHARPE   stored(PathA): {desc([float(stored[s]['sharpe']) for s in common if stored[s]['sharpe'] is not None])}")
    print(f"           canonical    : {desc([uni[s]['sharpe'] for s in common])}")
    # win_rate: stored Path B per-bar vs canonical per-trade
    print(f"  WIN_RATE stored(PathB per-bar): {desc([float(stored[s]['win_rate']) for s in common if stored[s]['win_rate'] is not None])}")
    print(f"           canonical (per-trade): {desc([uni[s]['win_rate'] for s in common])}")
    # max_drawdown: stored ×100 vs canonical fraction
    print(f"  MAXDD    stored(x100): {desc([float(stored[s]['max_drawdown']) for s in common if stored[s]['max_drawdown'] is not None])}")
    print(f"           canonical(frac): {desc([uni[s]['max_drawdown'] for s in common])}")
    # total_return sign agreement (Path B stored vs canonical ledger)
    pairs=[(stot(stored[s]), uni[s]['total_return']) for s in common if stot(stored[s]) is not None]
    agree=sum(1 for a,b in pairs if (a>=0)==(b>=0))
    print(f"  TOTAL_RETURN sign agreement (storedB vs canonical): {agree}/{len(pairs)} ({100*agree/len(pairs):.1f}%)")
    print(f"           stored(B): {desc([a for a,_ in pairs])}")
    print(f"           canonical: {desc([b for _,b in pairs])}")
    # deployability under canonical: net-positive count
    netpos=sum(1 for m in uni.values() if m['total_return']>0)
    print(f"\n  canonical net-positive strategies: {netpos}/{len(uni)} ({100*netpos/len(uni):.1f}%)")
    await c.close()

if __name__ == "__main__":
    asyncio.run(main())
