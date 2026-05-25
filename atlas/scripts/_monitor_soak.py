"""
Phase 26H Soak Monitor — runs alongside full_autonomous_cycle.py.
Samples DB every 5 minutes and logs metrics.
"""
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

async def sample(conn, checkpoint: int) -> dict:
    snap = {
        "checkpoint": checkpoint,
        "time": datetime.now(timezone.utc).isoformat(),
        # Section 1: Scout Network
        "scout_signals": 0,
        "scout_signals_new": 0,
        "source_diversity": 0,
        # Section 2: Ideator
        "influence_ideator": 0,
        # Section 3: Mutation
        "mutations": 0,
        # Section 4: Trust
        "trust_scores": {},
        # Section 5: Entropy
        "governance_events": 0,
        # Section 6: Strategies
        "strategies": 0,
        "avg_sharpe": 0.0,
        # Section 7: Execution
        "trades": 0,
        "total_pnl": 0.0,
        # Section 8: Attribution
        "attribution_events": 0,
        # Section 9: Stability
        "event_store_count": 0,
        "audit_ledger_count": 0,
    }

    try:
        # Baseline at checkpoint 0
        if checkpoint == 0:
            r = await conn.fetchrow("SELECT COUNT(*) FROM scout_signals")
            snap["_baseline_scout_signals"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COUNT(*) FROM strategies")
            snap["_baseline_strategies"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COUNT(*) FROM scout_influence_log")
            snap["_baseline_influence"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution")
            snap["_baseline_attribution"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COUNT(*) FROM event_store")
            snap["_baseline_event_store"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COUNT(*) FROM audit_ledger")
            snap["_baseline_audit"] = r[0] if r else 0
        else:
            snap["_baseline_scout_signals"] = 0
            snap["_baseline_strategies"] = 0
            snap["_baseline_influence"] = 0
            snap["_baseline_attribution"] = 0
            snap["_baseline_event_store"] = 0
            snap["_baseline_audit"] = 0

        # S1: Scout signals
        r = await conn.fetchrow("SELECT COUNT(*) FROM scout_signals")
        snap["scout_signals"] = r[0] if r else 0
        
        # Sources
        try:
            rows = await conn.fetch("SELECT source, COUNT(*) as cnt FROM scout_signals GROUP BY source")
            snap["source_diversity"] = len(rows)
        except:
            pass

        # S2: Ideator influence
        r = await conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "target_agent LIKE '%ideator%' OR target_agent LIKE '%Ideator%'"
        )
        snap["influence_ideator"] = r[0] if r else 0

        # S3: Mutations
        try:
            r = await conn.fetchrow("SELECT COUNT(*) FROM mutation_record")
            snap["mutations"] = r[0] if r else 0
        except:
            pass

        # S4: Trust
        try:
            rows = await conn.fetch(
                "SELECT source, dynamic_trust_score FROM source_performance_log "
                "ORDER BY updated_at DESC LIMIT 20"
            )
            snap["trust_scores"] = {str(r[0]): float(r[1]) for r in rows}
        except:
            pass

        # S5: Entropy governance
        r = await conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "source_scout = 'entropy_governance'"
        )
        snap["governance_events"] = r[0] if r else 0

        # S6: Strategies
        r = await conn.fetchrow("SELECT COUNT(*) FROM strategies")
        snap["strategies"] = r[0] if r else 0
        
        try:
            r = await conn.fetchrow(
                "SELECT COALESCE(AVG(sharpe),0) FROM backtest_results"
            )
            snap["avg_sharpe"] = float(r[0] or 0)
        except:
            pass

        # S7: Execution
        try:
            r = await conn.fetchrow("SELECT COUNT(*) FROM paper_trades")
            snap["trades"] = r[0] if r else 0
            r = await conn.fetchrow("SELECT COALESCE(SUM(pnl),0) FROM paper_trades")
            snap["total_pnl"] = float(r[0] or 0)
        except:
            pass

        # S8: Attribution
        r = await conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution")
        snap["attribution_events"] = r[0] if r else 0

        # S9: Event store & audit
        try:
            r = await conn.fetchrow("SELECT COUNT(*) FROM event_store")
            snap["event_store_count"] = r[0] if r else 0
        except:
            pass
        try:
            r = await conn.fetchrow("SELECT COUNT(*) FROM audit_ledger")
            snap["audit_ledger_count"] = r[0] if r else 0
        except:
            pass

        # Compute deltas if we have baseline
        if checkpoint > 0:
            snap["new_scout_signals"] = snap["scout_signals"] - snap.get("_baseline_scout_signals", snap["scout_signals"])
            snap["new_strategies"] = snap["strategies"] - snap.get("_baseline_strategies", snap["strategies"])
            snap["new_influence"] = snap["influence_ideator"] - snap.get("_baseline_influence", snap["influence_ideator"])
            snap["new_attribution"] = snap["attribution_events"] - snap.get("_baseline_attribution", snap["attribution_events"])
        else:
            snap["new_scout_signals"] = snap["scout_signals"]
            snap["new_strategies"] = snap["strategies"]
            snap["new_influence"] = snap["influence_ideator"]
            snap["new_attribution"] = snap["attribution_events"]

    except Exception as e:
        print(f"  ERROR sampling: {e}")

    return snap


async def main():
    import asyncpg
    from atlas.config.settings import get_settings
    
    settings = get_settings()
    db_url = re.sub(r'\+\w+', '', settings.database_url)
    
    conn = await asyncpg.connect(db_url)
    print(f"=== PHASE 26H SOAK MONITOR STARTED at {datetime.now(timezone.utc).isoformat()} ===")
    
    total_checks = 13  # 60 minutes / 5 minutes ≈ 12, plus baseline
    for i in range(total_checks):
        snap = await sample(conn, i)
        
        delta_ss = snap.get("new_scout_signals", 0)
        delta_strat = snap.get("new_strategies", 0)
        delta_inf = snap.get("new_influence", 0)
        
        print(f"[{snap['time'][11:19]}] CP{i}: "
              f"scout_sig={snap['scout_signals']}(+{delta_ss}), "
              f"strategies={snap['strategies']}(+{delta_strat}), "
              f"influence={snap['influence_ideator']}(+{delta_inf}), "
              f"attribution={snap['attribution_events']}(+{snap.get('new_attribution',0)}), "
              f"trades={snap['trades']}, "
              f"governance={snap['governance_events']}, "
              f"trust_srcs={len(snap.get('trust_scores', {}))}, "
              f"sharpe={snap['avg_sharpe']:.2f}")
        
        if i < total_checks - 1:
            await asyncio.sleep(300)  # 5 minutes
    
    await conn.close()
    print("=== MONITORING COMPLETE ===")


asyncio.run(main())
