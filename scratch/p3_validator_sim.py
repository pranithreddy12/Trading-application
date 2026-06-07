"""
P3 validator simulation — apply candidate policies to historical population. SHADOW ONLY.
Consumes frozen ledger_metrics_v1 + P2 fitness (cost^0.75, deploy_thresh 35, op_tol 0.5).
Validator = policy: significance floor + coverage + tiering. No fitness recompute.
"""
import asyncio, os, re, sys, math, statistics as st
from datetime import datetime, timedelta, timezone
import asyncpg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger_metrics import compute_ledger_metrics, dsn, ROUNDTRIP, SIZE

def clip(x,lo=0.0,hi=1.0): return max(lo,min(hi,x))
def Phi(x): return 0.5*(1.0+math.erf(x/math.sqrt(2.0)))
SHARPE_TARGET,E_TARGET,DD_TOL,OP_TOL,COST_EXP=2.0,0.001,0.25,0.5,0.75
N_HARD,N_FULL,TPD_OK,TPD_MAX=10,100,20,200
DEPLOY_THRESH=35  # frozen from P2

def fit(trades, wf, mc, rg, overfit):
    m=compute_ledger_metrics(trades)
    if m.get("n_trades",0)<2: return None
    sh=clip(m["sharpe"]/SHARPE_TARGET); pf=clip((m["profit_factor"]-1)/1)
    ex=clip(m["expectancy"]/E_TARGET); dd=clip(1+m["max_drawdown"]/DD_TOL)
    pq=(0.22*sh+0.16*pf+0.12*ex+0.10*dd)/0.60
    robust=(0.18*(wf or 0)+0.12*(mc or 0)+0.10*(rg or 0))/0.40
    Q=0.60*pq+0.40*robust
    N=m["n_trades"]; ng=0.0 if N<N_HARD else clip((N-N_HARD)/(N_FULL-N_HARD))
    r=[(float(t["pnl_pct"])-ROUNDTRIP)*SIZE for t in trades]
    mu=st.mean(r); sd=st.pstdev(r) if len(r)>1 else 0.0
    tt=(mu/sd)*math.sqrt(N) if sd>1e-12 else 0.0
    sig=ng*clip((Phi(tt)-0.5)/0.45)
    og=0.3 if overfit is None else clip(1-overfit/OP_TOL)
    ge=m["gross_edge"]; ret=0.0 if ge<=0 else clip(m["total_return"]/ge)
    span=max((trades[-1]["exit_time"]-trades[0]["entry_time"]).total_seconds()/86400,0.5)
    churn=clip(1-((N/span)-TPD_OK)/(TPD_MAX-TPD_OK)) if (N/span)>TPD_OK else 1.0
    M=sig*og*(ret**COST_EXP)*churn
    return dict(research=100*Q, deploy=100*Q*M, n=N, overfit=overfit, gross=ge)

def classify(f, cov_ok, min_floor, prod_floor, elite_band, research_band):
    if not cov_ok: return "pending_validation"
    sig_ok = f["n"] >= min_floor
    if f["deploy"]>=elite_band and f["n"]>=prod_floor and sig_ok: return "elite"
    if f["deploy"]>=DEPLOY_THRESH and sig_ok: return "validated"
    if f["research"]>=research_band: return "research_candidate"
    return "failed_validation"

def mk(pnls,days=30):
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

    pop={}
    for sid,tr in by.items():
        if len(tr)<2: continue
        f=fit(sorted(tr,key=lambda t:t["entry_time"]), wf.get(sid),mc.get(sid),rg.get(sid),od.get(sid))
        if f:
            cov = sid in wf and sid in mc and sid in rg and sid in od
            pop[sid]=(f,cov)
    n=len(pop)
    print(f"=== P3 VALIDATOR SIMULATION — {n} strategies ===")

    # current broken baseline (DB statuses)
    cur=await c.fetch("SELECT status, count(*) n FROM strategies WHERE status IN ('validated','elite') GROUP BY 1")
    curv=sum(r['n'] for r in cur)
    print(f"\n CURRENT (broken) policy: validated/elite={curv} (audit: ~213/222 underpowered <50 trades)")

    GOOD=fit(mk([0.008+0.004*((i%5)/4) for i in range(120)]),0.6,0.7,0.5,0.1)
    ELITE_BAND=60

    for min_floor in (50,100):
        for research_band in (30,40):
            counts={}; underpowered=0; junk=0
            for sid,(f,cov) in pop.items():
                stt=classify(f,cov,min_floor,100,ELITE_BAND,research_band)
                counts[stt]=counts.get(stt,0)+1
                if stt in ("validated","elite"):
                    if f["n"]<min_floor: underpowered+=1
                    if (f["overfit"] or 0)>=0.5 or f["gross"]<=0 or f["n"]<10: junk+=1
            good_status=classify(GOOD,True,min_floor,100,ELITE_BAND,research_band)
            print(f"\n --- MIN_FLOOR={min_floor} RESEARCH_BAND={research_band} ELITE_BAND={ELITE_BAND} ---")
            for s in ("elite","validated","research_candidate","pending_validation","failed_validation"):
                print(f"     {s:20} {counts.get(s,0)}")
            print(f"     [P3-H1] underpowered in validated/elite: {underpowered}  (target 0; current ~213)")
            print(f"     [P3-H2] junk in validated/elite:        {junk}  (target 0)")
            print(f"     [P3-H3] research_candidate populated:   {counts.get('research_candidate',0)>0}")
            print(f"     [P3-H4] GENUINE-good control ->         {good_status}  (want validated/elite)")
    # coverage stats
    covn=sum(1 for _,(f,cov) in pop.items() if cov)
    print(f"\n [P3-H5] coverage: {covn}/{n} have all 4 advanced validators ({100*covn/n:.0f}%); rest -> pending_validation")
    await c.close()

if __name__=="__main__":
    asyncio.run(main())
