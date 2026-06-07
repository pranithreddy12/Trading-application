"""
P2 B2.6 — parameter calibration sweep. SHADOW ONLY.
Objective: operating point where GENUINE-good passes AND junk stays 0 (not max passes).
Sweep: cost_gate = retention^k (k in 1.0,0.75,0.5); deploy threshold; overfit cutoff.
Significance gate NOT calibrated (P3 owns thresholds).
"""
import asyncio, os, re, sys, math, statistics as st
from datetime import datetime, timedelta, timezone
import asyncpg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger_metrics import compute_ledger_metrics, dsn, ROUNDTRIP, SIZE

def clip(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))
def Phi(x): return 0.5*(1.0+math.erf(x/math.sqrt(2.0)))

SHARPE_TARGET, E_TARGET, DD_TOL = 2.0, 0.001, 0.25
N_HARD, N_FULL, TPD_OK, TPD_MAX = 10, 100, 20, 200

def fitness(trades, wf, mc, regime, overfit, cost_exp=1.0, op_tol=0.5):
    m=compute_ledger_metrics(trades)
    if m.get("n_trades",0)<2: return None
    sharpe_s=clip(m["sharpe"]/SHARPE_TARGET); pf_s=clip((m["profit_factor"]-1)/1)
    exp_s=clip(m["expectancy"]/E_TARGET); dd_s=clip(1+m["max_drawdown"]/DD_TOL)
    pq=(0.22*sharpe_s+0.16*pf_s+0.12*exp_s+0.10*dd_s)/0.60
    robust=(0.18*(wf or 0)+0.12*(mc or 0)+0.10*(regime or 0))/0.40
    Q=0.60*pq+0.40*robust
    N=m["n_trades"]
    n_gate=0.0 if N<N_HARD else clip((N-N_HARD)/(N_FULL-N_HARD))
    r=[(float(t["pnl_pct"])-ROUNDTRIP)*SIZE for t in trades]
    mu=st.mean(r); sd=st.pstdev(r) if len(r)>1 else 0.0
    t=(mu/sd)*math.sqrt(N) if sd>1e-12 else 0.0
    sig=n_gate*clip((Phi(t)-0.5)/0.45)
    og=0.3 if overfit is None else clip(1-overfit/op_tol)
    ge=m["gross_edge"]; retention=0.0 if ge<=0 else clip(m["total_return"]/ge)
    span=max((trades[-1]["exit_time"]-trades[0]["entry_time"]).total_seconds()/86400,0.5)
    tpd=N/span; churn=clip(1-(tpd-TPD_OK)/(TPD_MAX-TPD_OK)) if tpd>TPD_OK else 1.0
    cost=(retention**cost_exp)*churn
    M=sig*og*cost
    return 100*Q*M

def mk(pnls, days=30):
    base=datetime(2026,1,1,tzinfo=timezone.utc); out=[]
    for i,p in enumerate(pnls):
        t0=base+timedelta(days=days*i/max(len(pnls),1))
        out.append(dict(pnl_pct=p,bars_held=10,entry_time=t0,exit_time=t0+timedelta(minutes=10)))
    return out

async def main():
    c=await asyncpg.connect(dsn())
    rows=await c.fetch("SELECT strategy_id, pnl_pct, bars_held, entry_time, exit_time FROM backtest_trades")
    by={}
    for r in rows: by.setdefault(str(r["strategy_id"]),[]).append(dict(pnl_pct=r["pnl_pct"],bars_held=r["bars_held"],entry_time=r["entry_time"],exit_time=r["exit_time"]))
    wf={str(r['strategy_id']):float(r['walk_forward_score']) for r in await c.fetch("SELECT DISTINCT ON (strategy_id) strategy_id, walk_forward_score FROM walk_forward_analysis ORDER BY strategy_id, analyzed_at DESC") if r['walk_forward_score'] is not None}
    mc={str(r['strategy_id']):float(r['monte_carlo_survival_score']) for r in await c.fetch("SELECT DISTINCT ON (strategy_id) strategy_id, monte_carlo_survival_score FROM monte_carlo_analysis ORDER BY strategy_id, simulated_at DESC") if r['monte_carlo_survival_score'] is not None}
    rg={str(r['strategy_id']):float(r['regime_survival_score']) for r in await c.fetch("SELECT DISTINCT ON (strategy_id) strategy_id, regime_survival_score FROM regime_validation ORDER BY strategy_id, validated_at DESC") if r['regime_survival_score'] is not None}
    od={str(r['strategy_id']):float(r['overfit_probability']) for r in await c.fetch("SELECT DISTINCT ON (strategy_id) strategy_id, overfit_probability FROM overfitting_analysis ORDER BY strategy_id, analyzed_at DESC") if r['overfit_probability'] is not None}
    reals=[(s,sorted(tr,key=lambda t:t["entry_time"])) for s,tr in by.items() if len(tr)>=2]

    GOOD=mk([0.008+0.004*((i%5)/4) for i in range(120)])
    JUNK={"3-lucky":(mk([0.02,0.03,0.02]),None,None,None,0.1),
          "churn-trap":(mk([0.001]*200),0.3,0.4,0.3,0.2),
          "overfit":(mk([0.012]*120),0.6,0.7,0.5,1.0)}
    THRESH=[25,30,35,40,45,50,60]

    print("=== B2.6 CALIBRATION SWEEP (overfit cutoff=0.5) ===")
    for k in (1.0,0.75,0.5):
        gd=fitness(GOOD,0.6,0.7,0.5,0.1,cost_exp=k)
        jd={n:fitness(t,w,m2,r2,o,cost_exp=k) for n,(t,w,m2,r2,o) in JUNK.items()}
        rd=[fitness(tr,wf.get(s),mc.get(s),rg.get(s),od.get(s),cost_exp=k) for s,tr in reals]
        rd=[x for x in rd if x is not None]
        print(f"\n cost_gate=retention^{k}  | GENUINE-good deploy={gd:.1f} | junk deploys={{ {', '.join(f'{n}:{v:.1f}' for n,v in jd.items())} }}")
        print(f"   {'thresh':>7}{'good_pass':>11}{'junk_pass':>11}{'real_pass':>11}")
        for th in THRESH:
            gp="YES" if gd>=th else "no"
            jp=sum(1 for v in jd.values() if v>=th)
            rp=sum(1 for v in rd if v>=th)
            print(f"   {th:>7}{gp:>11}{jp:>11}{rp:>11}")

    print("\n=== OVERFIT-CUTOFF SENSITIVITY (cost^0.75) ===")
    for op in (0.4,0.5,0.6):
        gd=fitness(GOOD,0.6,0.7,0.5,0.1,cost_exp=0.75,op_tol=op)
        ov_junk=fitness(JUNK["overfit"][0],0.6,0.7,0.5,1.0,cost_exp=0.75,op_tol=op)
        rd=[fitness(tr,wf.get(s),mc.get(s),rg.get(s),od.get(s),cost_exp=0.75,op_tol=op) for s,tr in reals]
        rd=[x for x in rd if x is not None]
        print(f"   op_tol={op}: GENUINE-good={gd:.1f}  overfit-junk={ov_junk:.1f}  real_pass(>=35)={sum(1 for v in rd if v>=35)}")

    # characterize real passers at recommended point (cost^0.75, thresh 35)
    print("\n=== REAL strategies passing at (cost^0.75, threshold=35) — are they good or junk? ===")
    passers=[]
    for s,tr in reals:
        v=fitness(tr,wf.get(s),mc.get(s),rg.get(s),od.get(s),cost_exp=0.75)
        if v is not None and v>=35:
            m=compute_ledger_metrics(tr)
            passers.append((s,v,m["n_trades"],m["total_return"],od.get(s)))
    print(f"   real passers: {len(passers)}")
    for s,v,n,ret,ov in sorted(passers,key=lambda x:-x[1])[:12]:
        print(f"     {s[:8]} deploy={v:.1f} n_trades={n} net_return={ret:+.4f} overfit={ov}")
    await c.close()

if __name__=="__main__":
    asyncio.run(main())
