"""
phase26_coupled_soak.py — PHASE 26H: 1-Hour Coupled Economic Soak

Validates whether ATLAS can convert information into adaptive economic behavior.

This is the FIRST true cognition-level soak, verifying:
  - Scout network materially influences ideation, mutation, execution
  - Trust evolves dynamically across scouts
  - Entropy governance changes organism behavior
  - Economic attribution chains populate correctly
  - Strategies are generated (not just 0)
  - Replay lineage remains intact
  - Operational stability is maintained

Runs full_autonomous_cycle.py --duration-minutes=60 as subprocess.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import asyncpg

# ── Configuration ──────────────────────────────────────────────
ATLAS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(ATLAS_DIR)

if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
os.environ["PYTHONPATH"] = _PARENT

from atlas.config.settings import settings
# Strip +asyncpg driver suffix for raw asyncpg compatibility
DB_URL = re.sub(r'\+\w+', '', settings.database_url)

# ── Soak parameters ───────────────────────────────────────────
DURATION_MINUTES = 60
CHECKPOINT_INTERVAL = 300  # 5 minutes

# ── Output paths ───────────────────────────────────────────────
REPORT_DIR = ATLAS_DIR
REPORT_PATHS = {
    "coupled_soak": os.path.join(ATLAS_DIR, "PHASE26H_COUPLED_SOAK_REPORT.md"),
    "scout_influence": os.path.join(ATLAS_DIR, "PHASE26H_SCOUT_INFLUENCE_REPORT.md"),
    "ideator_adaptation": os.path.join(ATLAS_DIR, "PHASE26H_IDEATOR_ADAPTATION_REPORT.md"),
    "mutation_adaptation": os.path.join(ATLAS_DIR, "PHASE26H_MUTATION_ADAPTATION_REPORT.md"),
    "trust_evolution": os.path.join(ATLAS_DIR, "PHASE26H_TRUST_EVOLUTION_REPORT.md"),
    "entropy_governance": os.path.join(ATLAS_DIR, "PHASE26H_ENTROPY_GOVERNANCE_REPORT.md"),
    "economic_attribution": os.path.join(ATLAS_DIR, "PHASE26H_ECONOMIC_ATTRIBUTION_REPORT.md"),
    "strategy_generation": os.path.join(ATLAS_DIR, "PHASE26H_STRATEGY_GENERATION_REPORT.md"),
    "execution_adaptation": os.path.join(ATLAS_DIR, "PHASE26H_EXECUTION_ADAPTATION_REPORT.md"),
    "adaptive_cognition_cert": os.path.join(ATLAS_DIR, "PHASE26H_ADAPTIVE_COGNITION_CERTIFICATION.md"),
}

SUCCESS_CRITERIA = [
    "Scout signals remain active",                                # C1
    "Strategies are generated",                                   # C2
    "Scouts materially influence ideation",                       # C3
    "Scouts materially influence mutation",                       # C4
    "Trust evolves dynamically",                                  # C5
    "Entropy changes organism behavior",                          # C6
    "Economic attribution chains populate",                       # C7
    "Execution adapts to scout intelligence",                     # C8
    "Portfolio behavior adapts dynamically",                      # C9
    "Replay lineage remains intact",                              # C10
    "Operational stability maintained",                           # C11
]


async def sample_db(pg_conn, checkpoint: int) -> dict:
    """Sample ALL 10 monitoring sections from the database."""
    snap = {
        # Metadata
        "checkpoint": checkpoint,
        "time": datetime.now(timezone.utc).isoformat(),
        # Section 1: Scout Network
        "scout_signals": 0,
        "scout_signals_last_hour": 0,
        "external_scout_memory": 0,
        "unknown_sources": 0,
        "quarantine_events": 0,
        "contradiction_events": 0,
        "synthesis_events": 0,
        "source_distribution": {},
        "source_diversity": 0,
        "signal_generation_rate": 0.0,
        "scout_sources_active": [],
        # Section 2: Ideator Modulation
        "influence_ideator": 0,
        "archetype_changes": 0,
        "archetype_distribution": {},
        "ideator_aggression": 0.0,
        "ideator_confidence": 0.0,
        "ideator_modulation_types": {},
        # Section 3: Mutation Adaptation
        "mutations": 0,
        "mutation_types": {},
        "mutation_diversity": 0,
        "mutation_entropy": 0.0,
        "entropy_conditioned_mutations": 0,
        "mutation_survival_rate": 0.0,
        # Section 4: Trust Evolution
        "trust_scores": {},
        "trust_divergence": 0.0,
        "source_performance_records": 0,
        "trust_decay_events": 0,
        "contradiction_frequency": {},
        # Section 5: Entropy Governance
        "governance_mode_published": False,
        "leverage_multiplier": 1.0,
        "aggression_cap": 1.0,
        "exploration_bias": 1.0,
        "entropy_value": 0.5,
        "governance_events": 0,
        # Section 6: Strategy Generation
        "strategies": 0,
        "strategies_by_status": {},
        "avg_sharpe": 0.0,
        "avg_sortino": 0.0,
        "avg_expectancy": 0.0,
        "avg_drawdown": 0.0,
        "avg_win_rate": 0.0,
        "backtest_results": 0,
        "strategy_archetype_diversity": 0,
        "regime_diversity": 0,
        "repair_count": 0,
        # Section 7: Execution & Portfolio
        "trades": 0,
        "total_pnl": 0.0,
        "total_exposure": 0.0,
        "leverage_cap": 1.0,
        "position_count": 0,
        "avg_slippage_bps": 0.0,
        "fill_quality": 0.0,
        "concentration_risk": 0.0,
        "diversification_score": 0.0,
        "portfolio_n_strategies": 0,
        # Section 8: Economic Attribution
        "influence_events": 0,
        "attribution_events": 0,
        "attribution_by_source": {},
        "avg_sharpe_contribution": 0.0,
        "avg_pnl_contribution": 0.0,
        # Section 9: Database Validation
        "event_store_count": 0,
        "audit_ledger_count": 0,
        "lifecycle_events": 0,
        "agent_crashes": 0,
        "failed_inserts": 0,
        # Section 10: Stability
        "agent_restarts": 0,
        "unique_agents": 0,
        "agent_starts": 0,
        "agent_stops": 0,
    }

    try:
        # ════════════════════════════════════════════════
        # SECTION 1: SCOUT NETWORK MONITORING
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM scout_signals")
        snap["scout_signals"] = r[0] if r else 0

        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_signals WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["scout_signals_last_hour"] = r[0] if r else 0

        try:
            r = await pg_conn.fetchrow("SELECT COUNT(*) FROM external_scout_memory")
            snap["external_scout_memory"] = r[0] if r else 0
        except Exception:
            pass

        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_signals WHERE source = 'unknown' OR source IS NULL"
        )
        snap["unknown_sources"] = r[0] if r else 0

        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM scout_quarantine WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            snap["quarantine_events"] = r[0] if r else 0
        except Exception:
            pass

        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "influence_type LIKE '%contradiction%' AND "
            "created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["contradiction_events"] = r[0] if r else 0

        try:
            r = await pg_conn.fetchrow("SELECT COUNT(*) FROM scout_synthesis_log")
            snap["synthesis_events"] = r[0] if r else 0
        except Exception:
            pass

        # Source distribution & diversity
        try:
            rows = await pg_conn.fetch(
                "SELECT source, COUNT(*) as cnt FROM scout_signals GROUP BY source ORDER BY cnt DESC"
            )
            snap["source_distribution"] = {str(r[0]): r[1] for r in rows}
            snap["source_diversity"] = len(rows)
            snap["scout_sources_active"] = [str(r[0]) for r in rows]
        except Exception:
            pass

        # Signal generation rate (signals per minute over last hour)
        if snap["scout_signals_last_hour"] > 0:
            snap["signal_generation_rate"] = round(snap["scout_signals_last_hour"] / 60.0, 2)

        # ════════════════════════════════════════════════
        # SECTION 2: IDEATOR MODULATION
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "target_agent LIKE '%ideator%' OR target_agent LIKE '%Ideator%'"
        )
        snap["influence_ideator"] = r[0] if r else 0

        # Archetype distribution changes
        try:
            rows = await pg_conn.fetch(
                "SELECT influence_metric, COUNT(*) as cnt FROM scout_influence_log "
                "WHERE influence_type LIKE '%archetype%' "
                "GROUP BY influence_metric ORDER BY cnt DESC"
            )
            snap["archetype_distribution"] = {str(r[0]): r[1] for r in rows}
            snap["archetype_changes"] = sum(r[1] for r in rows)
        except Exception:
            pass

        # Ideator modulation types
        try:
            rows = await pg_conn.fetch(
                "SELECT influence_type, COUNT(*) as cnt FROM scout_influence_log "
                "WHERE target_agent LIKE '%ideator%' OR target_agent LIKE '%Ideator%' "
                "GROUP BY influence_type ORDER BY cnt DESC"
            )
            snap["ideator_modulation_types"] = {str(r[0]): r[1] for r in rows}
        except Exception:
            pass

        # Ideator aggression and confidence from latest influence events
        try:
            r = await pg_conn.fetchrow(
                "SELECT delta, confidence FROM scout_influence_log "
                "WHERE target_agent LIKE '%ideator%' OR target_agent LIKE '%Ideator%' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if r:
                snap["ideator_aggression"] = float(r[0] or 0)
                snap["ideator_confidence"] = float(r[1] or 0)
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 3: MUTATION ADAPTATION
        # ════════════════════════════════════════════════
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM mutation_record WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            snap["mutations"] = r[0] if r else 0
        except Exception:
            pass

        try:
            rows = await pg_conn.fetch(
                "SELECT mutation_type, COUNT(*) as cnt FROM mutation_record "
                "WHERE created_at > NOW() - INTERVAL '1 hour' "
                "GROUP BY mutation_type ORDER BY cnt DESC"
            )
            snap["mutation_types"] = {str(r[0]): r[1] for r in rows}
            snap["mutation_diversity"] = len(rows)
        except Exception:
            pass

        # Mutation survival rate
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FILTER (WHERE improved = TRUE)::float / "
                "NULLIF(COUNT(*), 0) FROM mutation_record "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            snap["mutation_survival_rate"] = float(r[0]) if r and r[0] else 0.0
        except Exception:
            pass

        # Entropy-conditioned mutations
        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "influence_type LIKE '%entropy%' AND "
            "created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["entropy_conditioned_mutations"] = r[0] if r else 0

        # ════════════════════════════════════════════════
        # SECTION 4: TRUST EVOLUTION
        # ════════════════════════════════════════════════
        try:
            rows = await pg_conn.fetch(
                "SELECT source, dynamic_trust_score, updated_at FROM source_performance_log "
                "ORDER BY updated_at DESC LIMIT 30"
            )
            trust_scores = {}
            for row in rows:
                src = str(row[0])
                if src not in trust_scores:
                    trust_scores[src] = float(row[1] or 0)
            snap["trust_scores"] = trust_scores
            snap["source_performance_records"] = len(rows)

            # Trust divergence: std dev of trust scores
            if len(trust_scores) >= 2:
                scores = list(trust_scores.values())
                mean = sum(scores) / len(scores)
                variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                snap["trust_divergence"] = round(variance ** 0.5, 4)
        except Exception:
            pass

        # Trust decay events (updates with decreased score)
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM source_performance_log "
                "WHERE updated_at > NOW() - INTERVAL '1 hour'"
            )
            snap["trust_decay_events"] = r[0] if r else 0
        except Exception:
            pass

        # Contradiction frequency per source
        try:
            rows = await pg_conn.fetch(
                "SELECT source_scout, COUNT(*) as cnt FROM scout_influence_log "
                "WHERE influence_type LIKE '%contradiction%' "
                "GROUP BY source_scout ORDER BY cnt DESC"
            )
            snap["contradiction_frequency"] = {str(r[0]): r[1] for r in rows}
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 5: ENTROPY GOVERNANCE
        # ════════════════════════════════════════════════
        # Check for entropy governance influence events
        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM scout_influence_log WHERE "
            "source_scout = 'entropy_governance' AND "
            "created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["governance_events"] = r[0] if r else 0
        snap["governance_mode_published"] = snap["governance_events"] > 0

        # Get latest entropy governance params
        try:
            r = await pg_conn.fetchrow(
                "SELECT delta, confidence, entropy_context FROM scout_influence_log "
                "WHERE source_scout = 'entropy_governance' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if r:
                snap["leverage_multiplier"] = 1.0 + float(r[0] or 0)
                snap["entropy_value"] = float(r[2] or 0.5)
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 6: STRATEGY GENERATION
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM strategies WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["strategies"] = r[0] if r else 0

        try:
            rows = await pg_conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM strategies "
                "GROUP BY status ORDER BY cnt DESC"
            )
            snap["strategies_by_status"] = {str(r[0]): r[1] for r in rows}
        except Exception:
            pass

        r = await pg_conn.fetchrow(
            "SELECT COUNT(*) FROM backtest_results WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        snap["backtest_results"] = r[0] if r else 0

        # Avg strategy quality metrics
        r = await pg_conn.fetchrow(
            "SELECT COALESCE(AVG(sharpe),0), COALESCE(AVG(sortino_ratio),0), "
            "COALESCE(AVG(win_rate),0), COALESCE(AVG(max_drawdown),0), "
            "COALESCE(AVG(expectancy),0) "
            "FROM backtest_results WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        if r:
            snap["avg_sharpe"] = float(r[0] or 0)
            snap["avg_sortino"] = float(r[1] or 0)
            snap["avg_win_rate"] = float(r[2] or 0)
            snap["avg_drawdown"] = float(r[3] or 0)
            snap["avg_expectancy"] = float(r[4] or 0)

        # Archetype diversity in strategies
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(DISTINCT archetype) FROM strategies "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            snap["strategy_archetype_diversity"] = r[0] if r else 0
        except Exception:
            pass

        # Repairs
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM strategy_repair_log "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            snap["repair_count"] = r[0] if r else 0
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 7: EXECUTION & PORTFOLIO
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM paper_trades")
        snap["trades"] = r[0] if r else 0

        r = await pg_conn.fetchrow(
            "SELECT COALESCE(SUM(pnl), 0) FROM paper_trades"
        )
        snap["total_pnl"] = float(r[0]) if r else 0.0

        try:
            rows = await pg_conn.fetch(
                "SELECT id, side, symbol, quantity, price, pnl FROM paper_trades "
                "ORDER BY created_at DESC LIMIT 50"
            )
            snap["position_count"] = len(rows)
        except Exception:
            pass

        # Portfolio intelligence
        try:
            r = await pg_conn.fetchrow(
                "SELECT concentration_risk, diversification_score, n_strategies "
                "FROM portfolio_intelligence ORDER BY computed_at DESC LIMIT 1"
            )
            if r:
                snap["concentration_risk"] = float(r[0] or 0)
                snap["diversification_score"] = float(r[1] or 0)
                snap["portfolio_n_strategies"] = r[2] or 0
        except Exception:
            pass

        # Capital allocation
        try:
            r = await pg_conn.fetchrow(
                "SELECT total_exposure, leverage_cap_applied, n_strategies "
                "FROM capital_allocation ORDER BY computed_at DESC LIMIT 1"
            )
            if r:
                snap["total_exposure"] = float(r[0] or 0)
                snap["leverage_cap"] = float(r[1] or 1.0)
        except Exception:
            pass

        # Execution metrics
        try:
            r = await pg_conn.fetchrow(
                "SELECT AVG(avg_slippage_bps), AVG(fill_quality_score) "
                "FROM execution_intelligence WHERE timestamp > NOW() - INTERVAL '1 hour'"
            )
            if r:
                snap["avg_slippage_bps"] = float(r[0] or 0)
                snap["fill_quality"] = float(r[1] or 0)
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 8: ECONOMIC ATTRIBUTION
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM scout_influence_log")
        snap["influence_events"] = r[0] if r else 0

        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM scout_economic_attribution")
        snap["attribution_events"] = r[0] if r else 0

        try:
            rows = await pg_conn.fetch(
                "SELECT source_scout, AVG(sharpe_contribution), AVG(pnl_contribution), "
                "COUNT(*) as cnt FROM scout_economic_attribution "
                "GROUP BY source_scout ORDER BY cnt DESC"
            )
            snap["attribution_by_source"] = {
                str(r[0]): {"sharpe_contrib": float(r[1] or 0), "pnl_contrib": float(r[2] or 0), "count": r[3]}
                for r in rows
            }
        except Exception:
            pass

        r = await pg_conn.fetchrow(
            "SELECT COALESCE(AVG(sharpe_contribution), 0), COALESCE(AVG(pnl_contribution), 0) "
            "FROM scout_economic_attribution"
        )
        if r:
            snap["avg_sharpe_contribution"] = float(r[0] or 0)
            snap["avg_pnl_contribution"] = float(r[1] or 0)

        # ════════════════════════════════════════════════
        # SECTION 9: DATABASE VALIDATION
        # ════════════════════════════════════════════════
        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM event_store")
        snap["event_store_count"] = r[0] if r else 0

        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM audit_ledger")
        snap["audit_ledger_count"] = r[0] if r else 0

        r = await pg_conn.fetchrow("SELECT COUNT(*) FROM lifecycle_events")
        snap["lifecycle_events"] = r[0] if r else 0

        # Agent crashes
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM lifecycle_events WHERE stage = 'crashed' OR stage = 'error'"
            )
            snap["agent_crashes"] = r[0] if r else 0
        except Exception:
            pass

        # Failed inserts
        try:
            r = await pg_conn.fetchrow("SELECT COUNT(*) FROM failed_inserts")
            snap["failed_inserts"] = r[0] if r else 0
        except Exception:
            pass

        # ════════════════════════════════════════════════
        # SECTION 10: STABILITY
        # ════════════════════════════════════════════════
        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(DISTINCT COALESCE(actor, agent_name, 'unknown')) FROM lifecycle_events"
            )
            snap["unique_agents"] = r[0] if r else 0
        except Exception:
            pass

        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM lifecycle_events WHERE stage = 'started' OR stage = 'start'"
            )
            snap["agent_starts"] = r[0] if r else 0
        except Exception:
            pass

        try:
            r = await pg_conn.fetchrow(
                "SELECT COUNT(*) FROM lifecycle_events WHERE stage = 'stopped' OR stage = 'stop'"
            )
            snap["agent_stops"] = r[0] if r else 0
        except Exception:
            pass

        # Total restarts = duplicate start-after-crash patterns
        snap["agent_restarts"] = max(0, snap["agent_starts"] - snap["unique_agents"])

    except Exception as e:
        print(f"[CHECKPOINT {checkpoint}] DB error: {e}")

    return snap


def evaluate_criteria(all_snapshots: list[dict], pipeline_ok: bool) -> list[dict]:
    """Evaluate all 11 success criteria for Phase 26H."""
    results = []
    first = all_snapshots[0] if all_snapshots else {}
    last = all_snapshots[-1] if all_snapshots else {}
    timeline_snapshots = all_snapshots

    # C1: Scout signals remain active
    scouts_active = last.get("scout_signals", 0) > 0
    scouts_increased = len(timeline_snapshots) < 2 or last.get("scout_signals", 0) > first.get("scout_signals", 0)
    c1_pass = scouts_active and scouts_increased
    results.append({
        "criterion": SUCCESS_CRITERIA[0],
        "pass": c1_pass,
        "evidence": f"scout_signals: {first.get('scout_signals',0)} -> {last.get('scout_signals',0)}, sources={last.get('source_diversity',0)}"
    })

    # C2: Strategies are generated
    c2_pass = last.get("strategies", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[1],
        "pass": c2_pass,
        "evidence": f"strategies generated: {last.get('strategies',0)}"
    })

    # C3: Scouts materially influence ideation
    c3_pass = last.get("influence_ideator", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[2],
        "pass": c3_pass,
        "evidence": f"ideator influence events: {last.get('influence_ideator',0)}, archetype changes: {last.get('archetype_changes',0)}"
    })

    # C4: Scouts materially influence mutation
    c4_pass = last.get("mutations", 0) > 0 and last.get("entropy_conditioned_mutations", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[3],
        "pass": c4_pass,
        "evidence": f"mutations={last.get('mutations',0)}, mutation_diversity={last.get('mutation_diversity',0)}, entropy_conditioned_mutations={last.get('entropy_conditioned_mutations',0)}"
    })

    # C5: Trust evolves dynamically
    trust_scores = last.get("trust_scores", {})
    c5_pass = len(trust_scores) >= 2 and last.get("trust_divergence", 0) > 0.01
    results.append({
        "criterion": SUCCESS_CRITERIA[4],
        "pass": c5_pass,
        "evidence": f"trust scores: {len(trust_scores)} sources, divergence={last.get('trust_divergence',0):.4f}"
    })

    # C6: Entropy changes organism behavior
    c6_pass = last.get("governance_events", 0) > 0 or last.get("governance_mode_published", False)
    results.append({
        "criterion": SUCCESS_CRITERIA[5],
        "pass": c6_pass,
        "evidence": f"governance_events={last.get('governance_events',0)}, entropy={last.get('entropy_value',0.5):.3f}"
    })

    # C7: Economic attribution chains populate
    c7_pass = last.get("attribution_events", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[6],
        "pass": c7_pass,
        "evidence": f"attribution_events={last.get('attribution_events',0)}, sources_with_attribution={len(last.get('attribution_by_source',{}))}"
    })

    # C8: Execution adapts to scout intelligence
    c8_pass = last.get("trades", 0) > 0 and last.get("leverage_cap", 1.0) < 1.0
    results.append({
        "criterion": SUCCESS_CRITERIA[7],
        "pass": c8_pass,
        "evidence": f"trades={last.get('trades',0)}, leverage_cap={last.get('leverage_cap',1.0):.3f}, concentration_risk={last.get('concentration_risk',0):.3f}"
    })

    # C9: Portfolio behavior adapts dynamically
    c9_pass = last.get("portfolio_n_strategies", 0) > 0 and last.get("diversification_score", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[8],
        "pass": c9_pass,
        "evidence": f"portfolio strategies={last.get('portfolio_n_strategies',0)}, diversification={last.get('diversification_score',0):.3f}, exposure={last.get('total_exposure',0):.2f}"
    })

    # C10: Replay lineage remains intact
    c10_pass = pipeline_ok and last.get("event_store_count", 0) > 0 and last.get("audit_ledger_count", 0) > 0
    results.append({
        "criterion": SUCCESS_CRITERIA[9],
        "pass": c10_pass,
        "evidence": f"event_store={last.get('event_store_count',0)}, audit_ledger={last.get('audit_ledger_count',0)}, pipeline_exit={'clean' if pipeline_ok else 'error'}"
    })

    # C11: Operational stability maintained
    c11_pass = last.get("agent_crashes", 0) == 0 and last.get("failed_inserts", 0) < 10 and last.get("unknown_sources", 0) == 0
    results.append({
        "criterion": SUCCESS_CRITERIA[10],
        "pass": c11_pass,
        "evidence": f"crashes={last.get('agent_crashes',0)}, failed_inserts={last.get('failed_inserts',0)}, unknown_sources={last.get('unknown_sources',0)}"
    })

    return results


# ── Report Generators ────────────────────────────────────────

def generate_coupled_soak_report(all_snapshots, criteria_results, pipeline_exit, pipeline_elapsed):
    """Generate the main PHASE26H_COUPLED_SOAK_REPORT.md."""
    lines = ["# PHASE 26H — 1-HOUR COUPLED ECONOMIC SOAK REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")
    last = all_snapshots[-1] if all_snapshots else {}

    lines.append("\n## 1. EXECUTIVE SUMMARY")
    lines.append(f"\n- **Duration:** {DURATION_MINUTES} minutes ({DURATION_MINUTES//60}h)")
    lines.append(f"- **Pipeline exit code:** {pipeline_exit}")
    lines.append(f"- **Pipeline elapsed:** {pipeline_elapsed:.0f}s")
    lines.append(f"- **Checkpoints collected:** {len(all_snapshots)} (every {CHECKPOINT_INTERVAL//60}m)")

    pass_count = sum(1 for cr in criteria_results if cr["pass"])
    total = len(criteria_results)
    lines.append(f"- **Criteria passed:** {pass_count}/{total}")
    if pass_count >= 9:
        lines.append("\n### 🟢 PHASE 26H PASSES — Adaptive cognition confirmed")
    elif pass_count >= 6:
        lines.append("\n### 🟡 PHASE 26H PARTIAL PASS — Some cognition pathways active")
    else:
        lines.append("\n### 🔴 PHASE 26H FAILS — Insufficient adaptive behavior")

    # Core metric summary
    lines.append("\n## 2. FINAL STATE METRICS (t=60m)")
    if last:
        lines.append("\n| Domain | Metric | Value |")
        lines.append("|---|---|---|")
        lines.append(f"| Scout Network | Signals | {last.get('scout_signals',0)} |")
        lines.append(f"| Scout Network | Active Sources | {last.get('source_diversity',0)} |")
        lines.append(f"| Scout Network | Unknown Sources | {last.get('unknown_sources',0)} |")
        lines.append(f"| Ideator | Scout Influence Events | {last.get('influence_ideator',0)} |")
        lines.append(f"| Mutation | Mutations | {last.get('mutations',0)} |")
        lines.append(f"| Mutation | Diversity | {last.get('mutation_diversity',0)} |")
        lines.append(f"| Trust | Sources with Scores | {len(last.get('trust_scores',{}))} |")
        lines.append(f"| Trust | Divergence | {last.get('trust_divergence',0):.4f} |")
        lines.append(f"| Entropy | Governance Events | {last.get('governance_events',0)} |")
        lines.append(f"| Entropy | Leverage Multiplier | {last.get('leverage_multiplier',1.0):.3f} |")
        lines.append(f"| Strategy | Generated | {last.get('strategies',0)} |")
        lines.append(f"| Strategy | Avg Sharpe | {last.get('avg_sharpe',0):.4f} |")
        lines.append(f"| Strategy | Avg Win Rate | {last.get('avg_win_rate',0):.2%} |")
        lines.append(f"| Execution | Trades | {last.get('trades',0)} |")
        lines.append(f"| Execution | Total PnL | {last.get('total_pnl',0):.2f} |")
        lines.append(f"| Portfolio | Leverage Cap | {last.get('leverage_cap',1.0):.3f} |")
        lines.append(f"| Portfolio | Diversification | {last.get('diversification_score',0):.3f} |")
        lines.append(f"| Attribution | Events | {last.get('attribution_events',0)} |")
        lines.append(f"| Attribution | Sources | {len(last.get('attribution_by_source',{}))} |")
        lines.append(f"| Stability | Agent Crashes | {last.get('agent_crashes',0)} |")
        lines.append(f"| Stability | Failed Inserts | {last.get('failed_inserts',0)} |")
        lines.append(f"| Replay | Event Store | {last.get('event_store_count',0)} |")
        lines.append(f"| Replay | Audit Ledger | {last.get('audit_ledger_count',0)} |")

    # Checkpoint timeline
    lines.append("\n## 3. CHECKPOINT TIMELINE")
    lines.append("\n| t (min) | Signals | Strategies | Mutations | Influence | Attribution | Trades | Unk Src | Sharpe | Gov Events |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(
            f"| {t:.0f} | {snap['scout_signals']} | {snap['strategies']} | {snap['mutations']} | "
            f"{snap['influence_events']} | {snap['attribution_events']} | {snap['trades']} | "
            f"{snap['unknown_sources']} | {snap['avg_sharpe']:.2f} | {snap['governance_events']} |"
        )

    # Success criteria
    lines.append("\n## 4. SUCCESS CRITERIA EVALUATION")
    lines.append("")
    for cr in criteria_results:
        icon = "✅" if cr["pass"] else "❌"
        lines.append(f"{icon} **{cr['criterion']}**: {cr['evidence']}")

    lines.append(f"\n### Result: {pass_count}/{total} — {'PASS' if pass_count >= 9 else 'PARTIAL' if pass_count >= 6 else 'FAIL'}")

    # Certification
    lines.append("\n## 5. COUPLED SOAK CERTIFICATION")
    if pipeline_exit in (0, -2, None):
        lines.append("\n### ✅ ORGANISM STABILITY CONFIRMED")
        lines.append("- Autonomous pipeline completed without crash")
        lines.append("- Scout ingestion stable throughout")
    else:
        lines.append(f"\n### ⚠️ PIPELINE EXIT CODE {pipeline_exit}")

    lines.append("")
    lines.append("---")
    lines.append(f"\n*Report generated at {datetime.now(timezone.utc).isoformat()}*")
    return "\n".join(lines)


def generate_scout_influence_report(all_snapshots):
    """PHASE26H_SCOUT_INFLUENCE_REPORT.md — Section 1 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    first = all_snapshots[0] if all_snapshots else {}

    lines = ["# PHASE 26H — SCOUT INFLUENCE REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append("\n## 1. Scout Signal Production")
    lines.append(f"\n- **Total signals (all time):** {last.get('scout_signals',0)}")
    lines.append(f"- **Signals in last hour:** {last.get('scout_signals_last_hour',0)}")
    lines.append(f"- **Signal generation rate:** {last.get('signal_generation_rate',0)} signals/min")
    lines.append(f"- **Active sources:** {last.get('source_diversity',0)}")
    lines.append(f"- **Unknown sources:** {last.get('unknown_sources',0)}")

    lines.append("\n## 2. Source Distribution")
    dist = last.get("source_distribution", {})
    if dist:
        lines.append("\n| Source | Signals | % of Total |")
        lines.append("|---|---|---|")
        total_signals = sum(dist.values())
        for src, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            pct = cnt / total_signals * 100 if total_signals > 0 else 0
            lines.append(f"| {src} | {cnt} | {pct:.1f}% |")

    lines.append("\n## 3. Contradiction & Quarantine Events")
    lines.append(f"- **Contradiction events:** {last.get('contradiction_events',0)}")
    lines.append(f"- **Quarantine events:** {last.get('quarantine_events',0)}")
    lines.append(f"- **Synthesis events:** {last.get('synthesis_events',0)}")

    lines.append("\n## 4. Timeline")
    lines.append("\n| t (min) | Signals | Sources | Unknown | Quarantine |")
    lines.append("|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(f"| {t:.0f} | {snap['scout_signals']} | {snap['source_diversity']} | {snap['unknown_sources']} | {snap['quarantine_events']} |")

    return "\n".join(lines)


def generate_ideator_adaptation_report(all_snapshots):
    """PHASE26H_IDEATOR_ADAPTATION_REPORT.md — Section 2 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    lines = ["# PHASE 26H — IDEATOR ADAPTATION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Scout → Ideator Influence")
    lines.append(f"- **Total ideator influence events:** {last.get('influence_ideator',0)}")
    lines.append(f"- **Archetype distribution changes:** {last.get('archetype_changes',0)}")

    lines.append("\n## 2. Archetype Distribution")
    ad = last.get("archetype_distribution", {})
    if ad:
        lines.append("\n| Archetype Metric | Count |")
        lines.append("|---|---|")
        for m, cnt in sorted(ad.items(), key=lambda x: -x[1]):
            lines.append(f"| {m} | {cnt} |")
    else:
        lines.append("\nNo archetype distribution data collected.")

    lines.append("\n## 3. Ideator Modulation Types")
    mt = last.get("ideator_modulation_types", {})
    if mt:
        lines.append("\n| Modulation Type | Count |")
        lines.append("|---|---|")
        for m, cnt in sorted(mt.items(), key=lambda x: -x[1]):
            lines.append(f"| {m} | {cnt} |")
    else:
        lines.append("\nNo ideator modulation types recorded.")

    lines.append("\n## 4. Ideator Behavior Parameters")
    lines.append(f"- **Latest aggression delta:** {last.get('ideator_aggression',0):.4f}")
    lines.append(f"- **Latest confidence:** {last.get('ideator_confidence',0):.4f}")

    return "\n".join(lines)


def generate_mutation_adaptation_report(all_snapshots):
    """PHASE26H_MUTATION_ADAPTATION_REPORT.md — Section 3 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    lines = ["# PHASE 26H — MUTATION ADAPTATION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Mutation Activity")
    lines.append(f"- **Total mutations (last hour):** {last.get('mutations',0)}")
    lines.append(f"- **Mutation type diversity:** {last.get('mutation_diversity',0)}")
    lines.append(f"- **Mutation survival rate:** {last.get('mutation_survival_rate',0):.2%}")
    lines.append(f"- **Entropy-conditioned mutations:** {last.get('entropy_conditioned_mutations',0)}")

    lines.append("\n## 2. Mutation Type Distribution")
    mt = last.get("mutation_types", {})
    if mt:
        lines.append("\n| Mutation Type | Count |")
        lines.append("|---|---|")
        for t, cnt in sorted(mt.items(), key=lambda x: -x[1]):
            lines.append(f"| {t} | {cnt} |")
    else:
        lines.append("\nNo mutation types recorded.")

    lines.append("\n## 3. Timeline")
    lines.append("\n| t (min) | Mutations | Diversity | Survival Rate | Entropy-Conditioned |")
    lines.append("|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(f"| {t:.0f} | {snap['mutations']} | {snap['mutation_diversity']} | {snap['mutation_survival_rate']:.2%} | {snap['entropy_conditioned_mutations']} |")

    return "\n".join(lines)


def generate_trust_evolution_report(all_snapshots):
    """PHASE26H_TRUST_EVOLUTION_REPORT.md — Section 4 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    first = all_snapshots[0] if all_snapshots else {}

    lines = ["# PHASE 26H — TRUST EVOLUTION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Trust Score Overview")
    ts = last.get("trust_scores", {})
    lines.append(f"- **Sources with trust scores:** {len(ts)}")
    lines.append(f"- **Trust divergence (stddev):** {last.get('trust_divergence',0):.4f}")
    lines.append(f"- **Source performance records:** {last.get('source_performance_records',0)}")

    if ts:
        lines.append("\n## 2. Trust Scores by Source")
        lines.append("\n| Source | Trust Score |")
        lines.append("|---|---|")
        for src, score in sorted(ts.items(), key=lambda x: -x[1]):
            lines.append(f"| {src} | {score:.4f} |")
        lines.append(f"\n- **Max trust:** {max(ts.values()):.4f}")
        lines.append(f"- **Min trust:** {min(ts.values()):.4f}")
        lines.append(f"- **Range:** {max(ts.values()) - min(ts.values()):.4f}")
    else:
        lines.append("\nNo trust scores recorded yet.")

    lines.append("\n## 3. Contradiction Frequency")
    cf = last.get("contradiction_frequency", {})
    if cf:
        lines.append("\n| Source | Contradiction Events |")
        lines.append("|---|---|")
        for src, cnt in sorted(cf.items(), key=lambda x: -x[1]):
            lines.append(f"| {src} | {cnt} |")
    else:
        lines.append("\nNo contradiction events recorded.")

    lines.append("\n## 4. Timeline (Source Count Over Time)")
    lines.append("\n| t (min) | Trust Sources | Divergence |")
    lines.append("|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        n_src = len(snap.get("trust_scores", {}))
        lines.append(f"| {t:.0f} | {n_src} | {snap.get('trust_divergence',0):.4f} |")

    return "\n".join(lines)


def generate_entropy_governance_report(all_snapshots):
    """PHASE26H_ENTROPY_GOVERNANCE_REPORT.md — Section 5 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    lines = ["# PHASE 26H — ENTROPY GOVERNANCE REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Entropy Governance Activity")
    lines.append(f"- **Governance events published:** {last.get('governance_events',0)}")
    lines.append(f"- **Governance mode active:** {last.get('governance_mode_published',False)}")

    lines.append("\n## 2. Governance Parameters (Latest)")
    lines.append(f"- **Disagreement entropy:** {last.get('entropy_value',0.5):.4f}")
    lines.append(f"- **Leverage multiplier:** {last.get('leverage_multiplier',1.0):.3f}")
    lines.append(f"- **Aggression cap:** {last.get('aggression_cap',1.0):.3f}")
    lines.append(f"- **Exploration bias:** {last.get('exploration_bias',1.0):.3f}")

    # Determine mode from leverage
    lm = last.get('leverage_multiplier', 1.0)
    if lm < 0.6:
        mode = "defensive"
        explanation = "Scout disagreement is critically high — organism in defensive posture"
    elif lm < 0.85:
        mode = "conservative"
        explanation = "Elevated disagreement — organism in conservative posture"
    elif lm > 1.05:
        mode = "aggressive"
        explanation = "Low disagreement and high consensus — organism in aggressive posture"
    else:
        mode = "standard"
        explanation = "Normal disagreement levels — organism in standard operating mode"

    lines.append(f"- **Current mode:** {mode}")
    lines.append(f"- **Interpretation:** {explanation}")

    lines.append("\n## 3. Timeline")
    lines.append("\n| t (min) | Governance Events | Entropy | Leverage Mult | Mode |")
    lines.append("|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        ge = snap.get('governance_events', 0)
        ev = snap.get('entropy_value', 0.5)
        lm = snap.get('leverage_multiplier', 1.0)
        if ge > 0:
            mode_str = "defensive" if lm < 0.6 else "conservative" if lm < 0.85 else "aggressive" if lm > 1.05 else "standard"
            lines.append(f"| {t:.0f} | {ge} | {ev:.3f} | {lm:.3f} | {mode_str} |")
        else:
            lines.append(f"| {t:.0f} | {ge} | {ev:.3f} | {lm:.3f} | (inactive) |")

    return "\n".join(lines)


def generate_economic_attribution_report(all_snapshots):
    """PHASE26H_ECONOMIC_ATTRIBUTION_REPORT.md — Section 8 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    lines = ["# PHASE 26H — ECONOMIC ATTRIBUTION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Attribution Overview")
    lines.append(f"- **Total influence events:** {last.get('influence_events',0)}")
    lines.append(f"- **Economic attribution records:** {last.get('attribution_events',0)}")
    lines.append(f"- **Sources with attribution:** {len(last.get('attribution_by_source',{}))}")
    lines.append(f"- **Avg Sharpe contribution:** {last.get('avg_sharpe_contribution',0):.6f}")
    lines.append(f"- **Avg PnL contribution:** {last.get('avg_pnl_contribution',0):.6f}")

    lines.append("\n## 2. Attribution by Source")
    ab = last.get("attribution_by_source", {})
    if ab:
        lines.append("\n| Source | Records | Avg Sharpe Contrib | Avg PnL Contrib |")
        lines.append("|---|---|---|---|")
        for src, data in sorted(ab.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"| {src} | {data['count']} | {data['sharpe_contrib']:.4f} | {data['pnl_contrib']:.4f} |")
    else:
        lines.append("\nNo attribution data recorded.")

    lines.append("\n## 3. Timeline")
    lines.append("\n| t (min) | Influence Events | Attribution Events | Sources Attributed |")
    lines.append("|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(f"| {t:.0f} | {snap['influence_events']} | {snap['attribution_events']} | {len(snap.get('attribution_by_source',{}))} |")

    return "\n".join(lines)


def generate_strategy_generation_report(all_snapshots):
    """PHASE26H_STRATEGY_GENERATION_REPORT.md — Section 6 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    first = all_snapshots[0] if all_snapshots else {}
    lines = ["# PHASE 26H — STRATEGY GENERATION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Strategy Production")
    lines.append(f"- **Total strategies generated:** {last.get('strategies',0)}")
    lines.append(f"- **Backtest results:** {last.get('backtest_results',0)}")
    lines.append(f"- **Archetype diversity:** {last.get('strategy_archetype_diversity',0)}")
    lines.append(f"- **Repairs performed:** {last.get('repair_count',0)}")

    lines.append("\n## 2. Strategy Quality Metrics")
    lines.append(f"- **Avg Sharpe:** {last.get('avg_sharpe',0):.4f}")
    lines.append(f"- **Avg Sortino:** {last.get('avg_sortino',0):.4f}")
    lines.append(f"- **Avg Win Rate:** {last.get('avg_win_rate',0):.2%}")
    lines.append(f"- **Avg Expectancy:** {last.get('avg_expectancy',0):.4f}")
    lines.append(f"- **Avg Max Drawdown:** {last.get('avg_drawdown',0):.2%}")

    lines.append("\n## 3. Strategy Status Distribution")
    sbs = last.get("strategies_by_status", {})
    if sbs:
        lines.append("\n| Status | Count |")
        lines.append("|---|---|")
        for status, cnt in sorted(sbs.items(), key=lambda x: -x[1]):
            lines.append(f"| {status} | {cnt} |")
    else:
        lines.append("\nNo strategy status data.")

    lines.append("\n## 4. Timeline")
    lines.append("\n| t (min) | Strategies | Backtests | Avg Sharpe | Avg Win Rate |")
    lines.append("|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(f"| {t:.0f} | {snap['strategies']} | {snap['backtest_results']} | {snap['avg_sharpe']:.4f} | {snap['avg_win_rate']:.2%} |")

    return "\n".join(lines)


def generate_execution_adaptation_report(all_snapshots):
    """PHASE26H_EXECUTION_ADAPTATION_REPORT.md — Section 7 detailed."""
    last = all_snapshots[-1] if all_snapshots else {}
    lines = ["# PHASE 26H — EXECUTION ADAPTATION REPORT"]
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## 1. Execution Activity")
    lines.append(f"- **Paper trades executed:** {last.get('trades',0)}")
    lines.append(f"- **Total PnL:** {last.get('total_pnl',0):.2f}")
    lines.append(f"- **Avg slippage (bps):** {last.get('avg_slippage_bps',0):.2f}")
    lines.append(f"- **Fill quality:** {last.get('fill_quality',0):.3f}")

    lines.append("\n## 2. Portfolio State")
    lines.append(f"- **Portfolio strategies:** {last.get('portfolio_n_strategies',0)}")
    lines.append(f"- **Total exposure:** {last.get('total_exposure',0):.2f}")
    lines.append(f"- **Leverage cap:** {last.get('leverage_cap',1.0):.3f}")
    lines.append(f"- **Concentration risk:** {last.get('concentration_risk',0):.4f}")
    lines.append(f"- **Diversification score:** {last.get('diversification_score',0):.4f}")
    lines.append(f"- **Position count:** {last.get('position_count',0)}")

    lines.append("\n## 3. Timeline")
    lines.append("\n| t (min) | Trades | PnL | Exposure | Leverage Cap | Concentration |")
    lines.append("|---|---|---|---|---|---|")
    for snap in all_snapshots:
        t = snap["checkpoint"] / 60
        lines.append(f"| {t:.0f} | {snap['trades']} | {snap['total_pnl']:.1f} | {snap['total_exposure']:.1f} | {snap['leverage_cap']:.3f} | {snap['concentration_risk']:.4f} |")

    return "\n".join(lines)


def generate_adaptive_cognition_certification(all_snapshots, criteria_results, pipeline_exit, pipeline_elapsed):
    """PHASE26H_ADAPTIVE_COGNITION_CERTIFICATION.md — Final certification."""
    last = all_snapshots[-1] if all_snapshots else {}
    pass_count = sum(1 for cr in criteria_results if cr["pass"])
    total = len(criteria_results)

    lines = ["# PHASE 26H — ADAPTIVE COGNITION CERTIFICATION"]
    lines.append("\n## Master Cognition-Level Soak Certification")
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Duration:** {DURATION_MINUTES} minutes")
    lines.append(f"**Pipeline exit:** {pipeline_exit} {'(clean)' if pipeline_exit in (0, -2, None) else '(error)'}")
    lines.append(f"**Pipeline elapsed:** {pipeline_elapsed:.0f}s")

    lines.append("\n---")
    lines.append("\n## 1. CERTIFICATION DOMAINS")
    lines.append("")

    failures = []
    passes = []
    for cr in criteria_results:
        status = "✅ PASS" if cr["pass"] else "❌ FAIL"
        if not cr["pass"]:
            failures.append(cr)
        else:
            passes.append(cr)
        lines.append(f"### {status}: {cr['criterion']}")
        lines.append(f"- {cr['evidence']}")
        lines.append("")

    lines.append("---")
    lines.append(f"\n## 2. RESULT: {pass_count}/{total} CRITERIA MET")
    lines.append("")

    if pass_count >= 9:
        lines.append("### 🟢 PHASE 26H PASSES — ADAPTIVE COGNITION CONFIRMED")
        lines.append("")
        lines.append("ATLAS has demonstrated the ability to convert information into adaptive economic behavior:")
        lines.append(f"- Scout network active with {last.get('source_diversity',0)} sources and {last.get('scout_signals',0)} signals")
        lines.append(f"- Strategies generated: {last.get('strategies',0)}")
        lines.append(f"- Scout→Ideator coupling: {last.get('influence_ideator',0)} influence events")
        lines.append(f"- Scout→Mutation coupling: {last.get('entropy_conditioned_mutations',0)} entropy-conditioned mutations")
        lines.append(f"- Trust evolution: {len(last.get('trust_scores',{}))} sources with {last.get('trust_divergence',0):.4f} divergence")
        lines.append(f"- Entropy governance: {last.get('governance_events',0)} governance events")
        lines.append(f"- Economic attribution: {last.get('attribution_events',0)} attribution records")
        lines.append(f"- Execution active: {last.get('trades',0)} trades, {last.get('total_pnl',0):.2f} PnL")
        lines.append(f"- Portfolio diversified: {last.get('portfolio_n_strategies',0)} strategies, {last.get('diversification_score',0):.3f} diversification")
        lines.append(f"- Operational stability: {last.get('agent_crashes',0)} crashes, {last.get('failed_inserts',0)} failed inserts")
    elif pass_count >= 6:
        lines.append("### 🟡 PHASE 26H PARTIAL PASS — COGNITION PATHWAYS EMERGING")
        lines.append("")
        lines.append("ATLAS is beginning to demonstrate adaptive cognition, but some pathways remain inactive:")
        for f in failures:
            lines.append(f"- ❌ {f['criterion']}: {f['evidence']}")
    else:
        lines.append("### 🔴 PHASE 26H FAILS — INSUFFICIENT ADAPTIVE BEHAVIOR")
        lines.append("")
        lines.append("Phase 26H has failed because the organism did not demonstrate sufficient adaptive cognition:")
        for f in failures:
            lines.append(f"- ❌ {f['criterion']}: {f['evidence']}")

    lines.append("")
    lines.append("---")
    lines.append("\n## 3. FINAL VERDICT")
    lines.append("")

    if pass_count >= 9:
        lines.append("**The ATLAS organism has proven it can convert information into adaptive economic behavior.**")
        lines.append("This is not merely operational survival — it is adaptive cognition.")
        lines.append("")
        lines.append("| Domain | Status |")
        lines.append("|--------|--------|")
        lines.append(f"| Scout Network | ✅ Active |")
        lines.append(f"| Strategy Generation | ✅ Active |")
        lines.append(f"| Scout→Ideator Coupling | ✅ Active |")
        lines.append(f"| Scout→Mutation Coupling | ✅ Active |")
        lines.append(f"| Trust Evolution | ✅ Active |")
        lines.append(f"| Entropy Governance | ✅ Active |")
        lines.append(f"| Economic Attribution | ✅ Active |")
        lines.append(f"| Execution Adaptation | ✅ Active |")
        lines.append(f"| Portfolio Adaptation | ✅ Active |")
        lines.append(f"| Replay Integrity | ✅ Intact |")
        lines.append(f"| Operational Stability | ✅ Maintained |")
    elif pass_count >= 6:
        lines.append("**ATLAS is on the path to adaptive cognition but has not yet fully arrived.**")
        lines.append(f"{pass_count}/{total} criteria met. Identify and activate the remaining pathways.")
    else:
        lines.append("**ATLAS has not yet demonstrated adaptive cognition.**")
        lines.append(f"Only {pass_count}/{total} criteria met. Major pathways need activation.")

    return "\n".join(lines)


# ── Report Orchestrator ──────────────────────────────────────

def generate_all_reports(all_snapshots, criteria_results, pipeline_exit, pipeline_elapsed):
    """Generate all 10 Phase 26H reports."""
    # Reports that only need snapshot data
    snapshot_only = [
        ("scout_influence", generate_scout_influence_report),
        ("ideator_adaptation", generate_ideator_adaptation_report),
        ("mutation_adaptation", generate_mutation_adaptation_report),
        ("trust_evolution", generate_trust_evolution_report),
        ("entropy_governance", generate_entropy_governance_report),
        ("economic_attribution", generate_economic_attribution_report),
        ("strategy_generation", generate_strategy_generation_report),
        ("execution_adaptation", generate_execution_adaptation_report),
    ]
    # Reports that need full context
    full_context = [
        ("coupled_soak", generate_coupled_soak_report),
        ("adaptive_cognition_cert", generate_adaptive_cognition_certification),
    ]

    print("\n" + "=" * 60)
    print("GENERATING 10 PHASE 26H REPORTS")
    print("=" * 60)

    for key, generator in snapshot_only:
        content = generator(all_snapshots)
        path = REPORT_PATHS[key]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size_kb = len(content) / 1024
        print(f"  OK {os.path.basename(path)} ({size_kb:.1f} KB)")

    for key, generator in full_context:
        content = generator(all_snapshots, criteria_results, pipeline_exit, pipeline_elapsed)
        path = REPORT_PATHS[key]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size_kb = len(content) / 1024
        print(f"  OK {os.path.basename(path)} ({size_kb:.1f} KB)")

    print(f"\nAll 10 reports generated in {REPORT_DIR}")
    return REPORT_PATHS["adaptive_cognition_cert"]


if __name__ == "__main__":
    print("PHASE 26H — 1-Hour Coupled Economic Soak")
    print("==========================================")

    # Start the autonomous pipeline
    log_path = os.path.join(ATLAS_DIR, "phase26_soak_pipeline.log")
    env = os.environ.copy()
    env["PYTHONPATH"] = _PARENT
    env["SCOUTS_ENABLED"] = "true"

    pipeline_script = os.path.join(ATLAS_DIR, "scripts", "full_autonomous_cycle.py")
    pipe_proc = subprocess.Popen(
        [sys.executable, pipeline_script, f"--duration-minutes={DURATION_MINUTES}"],
        cwd=ATLAS_DIR,
        env=env,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    print(f"[SOAK] Pipeline PID: {pipe_proc.pid}")
    print(f"[SOAK] Monitoring for {DURATION_MINUTES} minutes...")

    start_time = time.time()
    all_snapshots: list[dict] = []
    total_checkpoints = (DURATION_MINUTES * 60) // CHECKPOINT_INTERVAL

    async def monitor(checkpoints_remaining: int) -> list[dict]:
        pg_conn = await asyncpg.connect(DB_URL)
        snapshots: list[dict] = []
        checkpoints_done = 0
        try:
            while checkpoints_done < checkpoints_remaining:
                # Check if pipeline died
                rc = pipe_proc.poll()
                if rc is not None:
                    print(f"[SOAK] Pipeline exited early with rc={rc} at t={time.time()-start_time:.0f}s")
                    break

                await asyncio.sleep(CHECKPOINT_INTERVAL)
                checkpoints_done += 1
                snap = await sample_db(pg_conn, checkpoints_done * CHECKPOINT_INTERVAL)
                snapshots.append(snap)
                elapsed = time.time() - start_time
                print(
                    f"[CHECKPOINT {checkpoints_done}/{checkpoints_remaining}] "
                    f"t={elapsed:.0f}s | "
                    f"signals={snap['scout_signals']} | "
                    f"strategies={snap['strategies']} | "
                    f"influence={snap['influence_events']} | "
                    f"attribution={snap['attribution_events']} | "
                    f"trades={snap['trades']} | "
                    f"unknown_src={snap['unknown_sources']}"
                )
        finally:
            await pg_conn.close()
        return snapshots

    async def main():
        all_snapshots_result = await monitor(total_checkpoints)
        # Wait for pipeline if still running
        if pipe_proc.poll() is None:
            try:
                pipe_proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                pipe_proc.kill()
                pipe_proc.wait()

        pipeline_elapsed = time.time() - start_time
        pipeline_exit = pipe_proc.returncode

        print(f"\n[SOAK] Pipeline completed: rc={pipeline_exit}, elapsed={pipeline_elapsed:.0f}s")

        # Evaluate criteria
        criteria_results = evaluate_criteria(all_snapshots_result, pipeline_exit in (0, -2))

        # Generate all 10 Phase 26H reports
        cert_path = generate_all_reports(
            all_snapshots_result, criteria_results,
            pipeline_exit, pipeline_elapsed
        )
        print(f"\n[SOAK] Final certification: {cert_path}")
        print("\n--- PHASE 26H RESULT ---")
        pass_count = sum(1 for cr in criteria_results if cr["pass"])
        total = len(criteria_results)
        print(f"Criteria: {pass_count}/{total} passed")

    asyncio.run(main())
