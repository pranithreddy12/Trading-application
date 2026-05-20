"""
Dashboard router — aggregated visibility endpoints for the operator UI.

Endpoints:
  GET /dashboard/              — Serve single-page HTML dashboard
  GET /dashboard/api/overview  — System health + agent + DB stats
  GET /dashboard/api/pipeline  — Strategy lifecycle funnel counts
  GET /dashboard/api/traces    — Recent lifecycle traces
  GET /dashboard/api/patterns  — Pattern intelligence summary
  GET /dashboard/api/risk      — Risk + CopyTrader snapshot
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from atlas.config.settings import settings

router = APIRouter(tags=["Dashboard"])


async def _get_db():
    from atlas.data.storage.timescale_client import TimescaleClient

    db = TimescaleClient(settings.database_url)
    await db.connect()
    return db


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    from pathlib import Path

    html_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@router.get("/dashboard/api/overview")
async def dashboard_overview():
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM strategies"))
            total_strategies = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM backtest_results"))
            total_backtests = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM lifecycle_events"))
            total_events = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(DISTINCT trace_id) FROM lifecycle_events")
            )
            total_traces = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM pattern_memory"))
            total_patterns = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM intelligence_briefs"))
            total_briefs = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
            total_trades = r.scalar() or 0

            r = await conn.execute(
                text("""
                SELECT status, COUNT(*) as cnt FROM strategies
                GROUP BY status ORDER BY cnt DESC LIMIT 10
            """)
            )
            status_counts = {row[0]: row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("SELECT COUNT(*) FROM api_keys WHERE revoked_at IS NULL")
            )
            active_keys = r.scalar() or 0            # Phase 12 portfolio intelligence stats
            r = await conn.execute(
                text("SELECT COUNT(*) FROM portfolio_intelligence")
            )
            portfolio_intel_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM capital_allocation")
            )
            alloc_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM drift_detection")
            )
            drift_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM strategy_retirement")
            )
            retirement_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM execution_realism")
            )
            realism_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM ensemble_execution")
            )
            ensemble_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM external_scout_memory")
            )
            scout_signals = r.scalar() or 0

            # Phase 11 validation stats
            r = await conn.execute(
                text("SELECT COUNT(*) FROM walk_forward_analysis")
            )
            wfa_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM monte_carlo_analysis")
            )
            mc_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM overfitting_analysis")
            )
            overfit_count = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM feature_importance")
            )
            fi_count = r.scalar() or 0

        # Health check (lightweight — doesn't start API)
        health_status = "ok"

        return {
            "system": {
                "status": health_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "api_version": "1.0.0",
            },
            "strategies": {
                "total": total_strategies,
                "by_status": status_counts,
            },
            "backtests": {
                "total": total_backtests,
            },
            "lineage": {
                "total_events": total_events,
                "total_traces": total_traces,
            },
            "patterns": {
                "total": total_patterns,
            },
            "briefs": {
                "total": total_briefs,
            },
            "execution": {
                "total_paper_trades": total_trades,
            },
            "auth": {
                "active_api_keys": active_keys,
            },
            "portfolio": {
                "intel_runs": portfolio_intel_count,
                "allocations": alloc_count,
                "ensemble_trades": ensemble_count,
            },
            "validation": {
                "walk_forward": wfa_count,
                "monte_carlo": mc_count,
                "overfitting": overfit_count,
                "feature_importance": fi_count,
            },
            "monitoring": {
                "drift_events": drift_count,
                "retirement_scans": retirement_count,
                "execution_realism": realism_count,
            },
            "scouts": {
                "external_signals": scout_signals,
            },
        }
    except Exception as exc:
        logger.error(f"Dashboard overview error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/pipeline")
async def dashboard_pipeline():
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT status, COUNT(*) as cnt
                FROM strategies
                GROUP BY status
                ORDER BY cnt DESC
            """)
            )
            stages = {row[0]: row[1] for row in r.fetchall()}

            # Lifecycle stage counts
            r = await conn.execute(
                text("""
                SELECT stage, status, COUNT(*) as cnt
                FROM lifecycle_events
                GROUP BY stage, status
                ORDER BY stage, status
            """)
            )
            lifecycle = {}
            for row in r.fetchall():
                stage = row[0]
                if stage not in lifecycle:
                    lifecycle[stage] = {}
                lifecycle[stage][row[1]] = row[2]

            # Recent strategies
            r = await conn.execute(
                text("""
                SELECT id, name, status, author_agent, created_at
                FROM strategies
                ORDER BY created_at DESC
                LIMIT 20
            """)
            )
            recent = [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "status": row[2],
                    "author": row[3],
                    "created_at": row[4].isoformat()
                    if hasattr(row[4], "isoformat")
                    else str(row[4]),
                }
                for row in r.fetchall()
            ]

        return {
            "strategy_statuses": stages,
            "lifecycle_events": lifecycle,
            "recent_strategies": recent,
        }
    except Exception as exc:
        logger.error(f"Dashboard pipeline error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/traces")
async def dashboard_traces(limit: int = Query(20, ge=1, le=100)):
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT trace_id, stage, status, actor,
                       strategy_id, metadata, created_at
                FROM lifecycle_events
                ORDER BY created_at DESC
                LIMIT :limit
            """),
                {"limit": limit},
            )
            events = []
            for row in r.fetchall():
                meta = row[5]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                events.append(
                    {
                        "trace_id": str(row[0]),
                        "stage": str(row[1]),
                        "status": str(row[2]),
                        "actor": str(row[3]),
                        "strategy_id": str(row[4]) if row[4] else None,
                        "metadata": meta,
                        "created_at": row[6].isoformat()
                        if hasattr(row[6], "isoformat")
                        else str(row[6]),
                    }
                )

            r = await conn.execute(
                text("""
                SELECT trace_id, COUNT(*) as cnt
                FROM lifecycle_events
                GROUP BY trace_id
                ORDER BY cnt DESC
                LIMIT 10
            """)
            )
            top_traces = {str(row[0]): row[1] for row in r.fetchall()}

        return {
            "recent_events": events,
            "most_active_traces": top_traces,
        }
    except Exception as exc:
        logger.error(f"Dashboard traces error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/patterns")
async def dashboard_patterns():
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT pattern_type, COUNT(*) as cnt
                FROM pattern_memory
                GROUP BY pattern_type
                ORDER BY cnt DESC
            """)
            )
            by_type = {row[0]: row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("""
                SELECT id, pattern_type, archetype, composite_score_avg,
                       confidence_score, recommendation, detected_at
                FROM pattern_memory
                ORDER BY confidence_score DESC, composite_score_avg DESC
                LIMIT 20
            """)
            )
            patterns = []
            for row in r.fetchall():
                patterns.append(
                    {
                        "id": str(row[0]),
                        "type": str(row[1]),
                        "archetype": str(row[2]) if row[2] else "unknown",
                        "composite_score": float(row[3]) if row[3] else 0.0,
                        "confidence": float(row[4]) if row[4] else 0.0,
                        "recommendation": str(row[5]) if row[5] else "",
                        "detected_at": row[6].isoformat()
                        if hasattr(row[6], "isoformat")
                        else str(row[6]),
                    }
                )

        return {
            "by_type": by_type,
            "patterns": patterns,
        }
    except Exception as exc:
        logger.error(f"Dashboard patterns error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/risk")
async def dashboard_risk():
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log"))
            copy_executions = r.scalar() or 0

            r = await conn.execute(
                text("""
                SELECT status, COUNT(*) as cnt
                FROM copy_execution_log
                GROUP BY status
            """)
            )
            copy_by_status = {row[0]: row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("""
                SELECT COUNT(*) FROM paper_trades WHERE status = 'open'
            """)
            )
            open_positions = r.scalar() or 0

            r = await conn.execute(
                text("""
                SELECT COALESCE(SUM(pnl), 0) FROM paper_trades
            """)
            )
            total_pnl = float(r.scalar() or 0.0)

            r = await conn.execute(
                text("SELECT COUNT(*) FROM copy_leader_accounts WHERE is_active = TRUE")
            )
            active_leaders = r.scalar() or 0

            r = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM copy_follower_accounts WHERE is_active = TRUE"
                )
            )
            active_followers = r.scalar() or 0

        # Check kill switch from DB
        try:
            r = await conn.execute(
                text("SELECT halted FROM risk_state WHERE scope = 'portfolio' LIMIT 1")
            )
            ks_active = bool(r.scalar() or False)
        except Exception:
            ks_active = False

        return {
            "copy_trader": {
                "total_executions": copy_executions,
                "by_status": copy_by_status,
                "active_leaders": active_leaders,
                "active_followers": active_followers,
            },
            "positions": {
                "open": open_positions,
            },
            "pnl": {
                "total": total_pnl,
            },
            "kill_switch": {
                "active": ks_active,
            },
        }
    except Exception as exc:
        logger.error(f"Dashboard risk error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/execution/logs")
async def dashboard_execution_logs(limit: int = Query(50, ge=1, le=200)):
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT order_key, strategy_id, symbol, side, quantity, price, 
                       state, broker, error_message, created_at 
                FROM execution_log 
                ORDER BY created_at DESC LIMIT :limit
                """),
                {"limit": limit}
            )
            logs = [dict(row._mapping) for row in r.fetchall()]
            for log in logs:
                if hasattr(log["created_at"], "isoformat"):
                    log["created_at"] = log["created_at"].isoformat()
                if log["strategy_id"]:
                    log["strategy_id"] = str(log["strategy_id"])
        return {"logs": logs}
    except Exception as exc:
        logger.error(f"Dashboard execution logs error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/portfolio")
async def dashboard_portfolio():
    """Phase 12 Portfolio Intelligence & Ensemble Execution data."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            # Latest portfolio intelligence
            pi = None
            r = await conn.execute(
                text("""
                SELECT computed_at, n_strategies, diversification_score,
                       concentration_risk, ensemble_survivability_score,
                       optimal_allocations
                FROM portfolio_intelligence
                ORDER BY computed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                pi = {
                    "computed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_strategies": row[1],
                    "diversification_score": float(row[2]) if row[2] else 0,
                    "concentration_risk": float(row[3]) if row[3] else 0,
                    "ensemble_survivability": float(row[4]) if row[4] else 0,
                }

            # Latest capital allocation
            ca = None
            r = await conn.execute(
                text("""
                SELECT computed_at, method, total_exposure, n_strategies
                FROM capital_allocation
                ORDER BY computed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                ca = {
                    "computed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "method": row[1],
                    "total_exposure": float(row[2]) if row[2] else 0,
                    "n_strategies": row[3],
                }

            # Recent ensemble trades
            r = await conn.execute(
                text("""
                SELECT executed_at, n_signals_processed, n_trades_generated
                FROM ensemble_execution
                ORDER BY executed_at DESC LIMIT 10
                """)
            )
            ensemble_trades = []
            for row in r.fetchall():
                ensemble_trades.append({
                    "executed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "signals": row[1],
                    "trades": row[2],
                })

        return {
            "portfolio_intelligence": pi,
            "capital_allocation": ca,
            "ensemble_trades": ensemble_trades,
        }
    except Exception as exc:
        logger.error(f"Dashboard portfolio error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/monitoring")
async def dashboard_monitoring():
    """Phase 12 Drift Detection & Strategy Retirement data."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            # Latest drift detection
            drift = None
            r = await conn.execute(
                text("""
                SELECT detected_at, feature_drift_score, strategy_drift_score,
                       regime_drift_score, composite_severity,
                       retrain_recommendations, retirement_candidates
                FROM drift_detection
                ORDER BY detected_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                drift = {
                    "detected_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "feature_drift": float(row[1]) if row[1] else 0,
                    "strategy_drift": float(row[2]) if row[2] else 0,
                    "regime_drift": float(row[3]) if row[3] else 0,
                    "composite_severity": float(row[4]) if row[4] else 0,
                }

            # Latest strategy retirement
            retirement = None
            r = await conn.execute(
                text("""
                SELECT analyzed_at, n_strategies_analyzed, n_retired,
                       n_monitor, n_retirement_pending
                FROM strategy_retirement
                ORDER BY analyzed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                retirement = {
                    "analyzed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_analyzed": row[1],
                    "n_retired": row[2],
                    "n_monitor": row[3],
                    "n_pending": row[4],
                }

        return {
            "drift": drift,
            "retirement": retirement,
        }
    except Exception as exc:
        logger.error(f"Dashboard monitoring error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/execution/realism")
async def dashboard_execution_realism():
    """Phase 12 Execution Realism Engine data."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT simulated_at, n_trades_simulated, avg_fill_probability,
                       avg_expected_slippage_bps, avg_simulated_latency_ms,
                       execution_degradation_score
                FROM execution_realism
                ORDER BY simulated_at DESC LIMIT 5
                """)
            )
            simulations = []
            for row in r.fetchall():
                simulations.append({
                    "simulated_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_trades": row[1],
                    "fill_prob": float(row[2]) if row[2] else 0,
                    "slippage_bps": float(row[3]) if row[3] else 0,
                    "latency_ms": float(row[4]) if row[4] else 0,
                    "degradation_score": float(row[5]) if row[5] else 0,
                })
        return {"simulations": simulations}
    except Exception as exc:
        logger.error(f"Dashboard execution realism error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/scouts")
async def dashboard_scouts():
    """Phase 12 External Scout Network data."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT source, COUNT(*) as cnt
                FROM external_scout_memory
                GROUP BY source ORDER BY cnt DESC
                """)
            )
            by_source = {str(row[0]): row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("""
                SELECT source, timestamp, sentiment, hypothesis_score,
                       signal_direction, mentioned_tickers
                FROM external_scout_memory
                ORDER BY timestamp DESC LIMIT 20
                """)
            )
            signals = []
            for row in r.fetchall():
                signals.append({
                    "source": str(row[0]),
                    "timestamp": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
                    "sentiment": float(row[2]) if row[2] else 0,
                    "score": float(row[3]) if row[3] else 0,
                    "direction": str(row[4]) if row[4] else "neutral",
                })
        return {"by_source": by_source, "signals": signals}
    except Exception as exc:
        logger.error(f"Dashboard scouts error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/validation")
async def dashboard_validation():
    """Phase 11 Advanced Validation summary."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            # Walk-forward
            wf = None
            r = await conn.execute(
                text("""
                SELECT walk_forward_score, temporal_consistency, regime_survival_score
                FROM walk_forward_analysis
                ORDER BY analyzed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                wf = {
                    "walk_forward_score": float(row[0]) if row[0] else 0,
                    "temporal_consistency": float(row[1]) if row[1] else 0,
                    "regime_survival_score": float(row[2]) if row[2] else 0,
                }

            # Monte Carlo
            mc = None
            r = await conn.execute(
                text("""
                SELECT monte_carlo_survival_score, expected_tail_drawdown,
                       probabilistic_sharpe, n_simulations
                FROM monte_carlo_analysis
                ORDER BY simulated_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                mc = {
                    "survival_score": float(row[0]) if row[0] else 0,
                    "tail_drawdown": float(row[1]) if row[1] else 0,
                    "prob_sharpe": float(row[2]) if row[2] else 0,
                    "n_simulations": row[3],
                }

            # Overfitting
            of = None
            r = await conn.execute(
                text("""
                SELECT overfit_probability, robustness_score, parameter_stability_score
                FROM overfitting_analysis
                ORDER BY analyzed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                of = {
                    "overfit_probability": float(row[0]) if row[0] else 0,
                    "robustness_score": float(row[1]) if row[1] else 0,
                    "stability_score": float(row[2]) if row[2] else 0,
                }

            # Regime validation
            rv = None
            r = await conn.execute(
                text("""
                SELECT regime_survival_score, regime_dependency_score,
                       n_regimes_survived, over_specialized
                FROM regime_validation
                ORDER BY validated_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                rv = {
                    "survival_score": float(row[0]) if row[0] else 0,
                    "dependency_score": float(row[1]) if row[1] else 0,
                    "n_regimes": row[2],
                    "over_specialized": bool(row[3]),
                }

            # Cost stress
            cs = None
            r = await conn.execute(
                text("""
                SELECT cost_survival_score, max_survivable_multiplier,
                       fragile_scalper_detected
                FROM cost_stress_analysis
                ORDER BY tested_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                cs = {
                    "survival_score": float(row[0]) if row[0] else 0,
                    "max_multiplier": float(row[1]) if row[1] else 0,
                    "fragile_scalper": bool(row[2]),
                }

        return {
            "walk_forward": wf,
            "monte_carlo": mc,
            "overfitting": of,
            "regime_validation": rv,
            "cost_stress": cs,
        }
    except Exception as exc:
        logger.error(f"Dashboard validation error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/features")
async def dashboard_features():
    """Phase 11 Feature Importance data."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT feature_name, feature_importance_score, n_uses,
                       survival_rate, dominant_archetype
                FROM feature_importance
                ORDER BY feature_importance_score DESC
                LIMIT 20
                """)
            )
            features = []
            for row in r.fetchall():
                features.append({
                    "name": str(row[0]),
                    "importance": float(row[1]) if row[1] else 0,
                    "n_uses": row[2],
                    "survival_rate": float(row[3]) if row[3] else 0,
                    "dominant_archetype": str(row[4]) if row[4] else "",
                })
        return {"features": features}
    except Exception as exc:
        logger.error(f"Dashboard features error: {exc}")
        return {"error": str(exc)}

@router.get("/dashboard/api/execution/dead-letters")
async def dashboard_dead_letters():
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT id, order_key, strategy_id, symbol, side, quantity, 
                       failure_reason, last_state, severity, created_at, retry_count
                FROM execution_dead_letter 
                WHERE resolved = FALSE 
                ORDER BY severity DESC, created_at DESC
                """)
            )
            dead_letters = [dict(row._mapping) for row in r.fetchall()]
            for dl in dead_letters:
                dl["id"] = str(dl["id"])
                if dl["strategy_id"]:
                    dl["strategy_id"] = str(dl["strategy_id"])
                if hasattr(dl["created_at"], "isoformat"):
                    dl["created_at"] = dl["created_at"].isoformat()
        return {"dead_letters": dead_letters}
    except Exception as exc:
        logger.error(f"Dashboard dead letters error: {exc}")
        return {"error": str(exc)}


# ================================================================
# PHASE 13 — PRODUCTION GOVERNANCE ENDPOINTS
# ================================================================

@router.get("/dashboard/api/governance/system-health")
async def dashboard_system_health():
    """Phase 13: Latest system health assessment."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT checked_at, composite_score, system_mode, degraded_subsystems, n_degraded
                FROM system_health
                ORDER BY checked_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "checked_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "composite_score": float(row[1]) if row[1] else 0,
                    "system_mode": row[2] or "normal",
                    "degraded_subsystems": row[3] if isinstance(row[3], (list, dict)) else [],
                    "n_degraded": row[4] or 0,
                }
            return {"message": "No health data"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/governance/event-store")
async def dashboard_event_store(limit: int = 20):
    """Phase 13: Event store replay timeline."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT id, aggregate_type, event_type, aggregate_id, trace_id, created_at
                FROM event_store
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            events = []
            for row in r.fetchall():
                events.append({
                    "id": str(row[0]),
                    "aggregate_type": row[1],
                    "event_type": row[2],
                    "aggregate_id": row[3],
                    "trace_id": row[4],
                    "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
                })
            r = await conn.execute(text("SELECT COUNT(*) FROM event_store"))
            total = r.scalar() or 0
        return {"total_events": total, "recent_events": events}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/governance/audit")
async def dashboard_audit(limit: int = 20):
    """Phase 13: Audit ledger entries."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT id, event_type, actor, action, target_id, trace_id, created_at
                FROM audit_ledger
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            entries = []
            for row in r.fetchall():
                entries.append({
                    "id": str(row[0]),
                    "event_type": row[1],
                    "actor": row[2],
                    "action": row[3],
                    "target_id": row[4],
                    "trace_id": row[5],
                    "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                })
            r = await conn.execute(text("SELECT COUNT(*) FROM audit_ledger"))
            total = r.scalar() or 0
        return {"total_entries": total, "entries": entries}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/governance/deployments")
async def dashboard_deployments(limit: int = 20):
    """Phase 13: Deployment governance records."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT id, strategy_id, mode, status, approved_by, activated_at
                FROM deployment_governance
                ORDER BY proposed_at DESC LIMIT :limit
            """), {"limit": limit})
            deploys = []
            for row in r.fetchall():
                deploys.append({
                    "id": str(row[0]),
                    "strategy_id": str(row[1]),
                    "mode": row[2],
                    "status": row[3],
                    "approved_by": row[4],
                    "activated_at": row[5].isoformat() if row[5] and hasattr(row[5], "isoformat") else str(row[5]) if row[5] else None,
                })
        return {"deployments": deploys}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/governance/replay-integrity")
async def dashboard_replay_integrity():
    """Phase 13: Latest replay integrity score."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT checked_at, n_aggregates_checked, integrity_score, n_violations
                FROM replay_integrity
                ORDER BY checked_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "checked_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_aggregates": row[1] or 0,
                    "integrity_score": float(row[2]) if row[2] else 0,
                    "n_violations": row[3] or 0,
                }
            return {"message": "No replay integrity data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 14 — PORTFOLIO DURABILITY ENDPOINTS
# ================================================================

@router.get("/dashboard/api/risk/systemic")
async def dashboard_systemic_risk():
    """Phase 14: Latest systemic risk assessment."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT assessed_at, systemic_risk_score, contagion_probability, portfolio_fragility
                FROM systemic_risk
                ORDER BY assessed_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "assessed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "systemic_risk_score": float(row[1]) if row[1] else 0,
                    "contagion_probability": float(row[2]) if row[2] else 0,
                    "portfolio_fragility": float(row[3]) if row[3] else 0,
                }
            return {"message": "No systemic risk data"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/risk/stress-test")
async def dashboard_stress_test():
    """Phase 14: Latest stress test results."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT tested_at, n_scenarios, worst_scenario, min_survival_probability, max_drawdown
                FROM stress_test_results
                ORDER BY tested_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "tested_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_scenarios": row[1] or 0,
                    "worst_scenario": row[2] or "",
                    "min_survival_prob": float(row[3]) if row[3] else 0,
                    "max_drawdown": float(row[4]) if row[4] else 0,
                }
            return {"message": "No stress test data"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/risk/capital-preservation")
async def dashboard_capital_preservation():
    """Phase 14: Latest capital preservation state."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT checked_at, drawdown_pct, action_taken, total_exposure
                FROM capital_preservation_state
                ORDER BY checked_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "checked_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "drawdown_pct": float(row[1]) if row[1] else 0,
                    "action_taken": row[2] or "none",
                    "total_exposure": float(row[3]) if row[3] else 0,
                }
            return {"message": "No capital preservation data"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/portfolio/optimizer")
async def dashboard_portfolio_optimizer():
    """Phase 14: Advanced portfolio optimizer results."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT optimized_at, method_used, n_strategies
                FROM advanced_portfolio_optimization
                ORDER BY optimized_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "optimized_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "method": row[1] or "",
                    "n_strategies": row[2] or 0,
                }
            return {"message": "No optimizer data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 15 — META-LEARNING ENDPOINTS
# ================================================================

@router.get("/dashboard/api/meta/prompts")
async def dashboard_prompts(limit: int = 20):
    """Phase 15: Prompt evolution templates."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT id, prompt_type, archetype, status, effectiveness_score, generation_count
                FROM prompt_templates
                ORDER BY effectiveness_score DESC
                LIMIT :limit
            """), {"limit": limit})
            prompts = []
            for row in r.fetchall():
                prompts.append({
                    "id": str(row[0]),
                    "type": row[1],
                    "archetype": row[2],
                    "status": row[3],
                    "effectiveness": float(row[4]) if row[4] else 0,
                    "generations": row[5] or 0,
                })
        return {"prompts": prompts}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/mutation-policy")
async def dashboard_mutation_policy():
    """Phase 15: Latest mutation policy state."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT learned_at, n_observations
                FROM mutation_policy_state
                ORDER BY learned_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "learned_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_observations": row[1] or 0,
                }
            return {"message": "No mutation policy data"}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/agent-governance")
async def dashboard_agent_governance():
    """Phase 15: Agent performance governor state."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT assessed_at, n_agents_assessed
                FROM agent_governance_state
                ORDER BY assessed_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                return {
                    "assessed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_agents_assessed": row[1] or 0,
                }
            return {"message": "No agent governance data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 17 — OBSERVABILITY ENDPOINTS
# ================================================================

@router.get("/dashboard/api/observability/metrics")
async def dashboard_metrics(limit: int = 20):
    """Phase 17: Monitoring fabric metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT recorded_at, counters, latencies
                FROM monitoring_metrics
                ORDER BY recorded_at DESC LIMIT :limit
            """), {"limit": limit})
            metrics = []
            for row in r.fetchall():
                metrics.append({
                    "recorded_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "counters": row[1] if isinstance(row[1], dict) else {},
                })
        return {"metrics": metrics}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/observability/anomalies")
async def dashboard_anomalies(limit: int = 20):
    """Phase 17: Anomaly observations."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT observed_at, n_anomalies, severity
                FROM anomaly_observations
                ORDER BY observed_at DESC LIMIT :limit
            """), {"limit": limit})
            anomalies = []
            for row in r.fetchall():
                anomalies.append({
                    "observed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "n_anomalies": row[1] or 0,
                    "severity": float(row[2]) if row[2] else 0,
                })
        return {"anomalies": anomalies}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 18 — DASHBOARD OVERVIEW ENHANCEMENT
# ================================================================

@router.get("/dashboard/api/overview/institutional")
async def dashboard_institutional_overview():
    """Phase 18: Institutional maturity metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            metrics = {}
            for tbl, label in [
                ("event_store", "events"),
                ("audit_ledger", "audit_entries"),
                ("system_health", "health_checks"),
                ("deployment_governance", "deployments"),
                ("systemic_risk", "risk_assessments"),
                ("stress_test_results", "stress_tests"),
                ("advanced_portfolio_optimization", "optimization_runs"),
                ("prompt_templates", "prompt_templates"),
                ("mutation_policy_state", "policy_learnings"),
                ("agent_governance_state", "governance_snapshots"),
                ("monitoring_metrics", "metric_points"),
                ("anomaly_observations", "anomaly_events"),
            ]:
                try:
                    r = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                    metrics[label] = r.scalar() or 0
                except Exception:
                    metrics[label] = 0
        return metrics
    except Exception as exc:
        return {"error": str(exc)}

# ================================================================
# PHASE 19 — META-INTELLIGENCE DASHBOARD ENDPOINTS
# ================================================================

@router.get("/dashboard/api/meta-reasoning")
async def dashboard_meta_reasoning(limit: int = Query(default=20, le=100)):
    """Phase 19B: Latest MetaReasoningAgent advisories."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT id, trace_id, advisory_type, confidence,
                       reasoning_text, recommendations,
                       metadata, created_at
                FROM meta_reasoning_log
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "advisories": [
                    {
                        "id": row[0], "trace_id": row[1],
                        "advisory_type": row[2],
                        "confidence": float(row[3]) if row[3] else 0,
                        "reasoning": row[4],
                        "recommendations": json.loads(row[5]) if isinstance(row[5], str) else (row[5] or []),
                        "metadata": json.loads(row[6]) if isinstance(row[6], str) else (row[6] or {}),
                        "created_at": str(row[7]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/hypotheses")
async def dashboard_hypotheses(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=30, le=100),
):
    """Phase 19C: Hypothesis registry with lifecycle status."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            if status:
                r = await conn.execute(text("""
                    SELECT id, trace_id, statement, observation_source,
                           confidence, evidence_count, contradiction_count,
                           status, regime_scope, decay_rate,
                           created_at, updated_at
                    FROM hypothesis_registry
                    WHERE status = :status
                    ORDER BY confidence DESC LIMIT :limit
                """), {"status": status, "limit": limit})
            else:
                r = await conn.execute(text("""
                    SELECT id, trace_id, statement, observation_source,
                           confidence, evidence_count, contradiction_count,
                           status, regime_scope, decay_rate,
                           created_at, updated_at
                    FROM hypothesis_registry
                    ORDER BY created_at DESC LIMIT :limit
                """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "hypotheses": [
                    {
                        "id": row[0], "trace_id": row[1],
                        "statement": row[2], "source": row[3],
                        "confidence": float(row[4]) if row[4] else 0,
                        "evidence_count": row[5] or 0,
                        "contradiction_count": row[6] or 0,
                        "status": row[7],
                        "regime_scope": row[8],
                        "decay_rate": float(row[9]) if row[9] else 0,
                        "created_at": str(row[10]),
                        "updated_at": str(row[11]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/failure-analysis")
async def dashboard_failure_analysis(limit: int = Query(default=10, le=50)):
    """Phase 19D: Recent failure diagnoses."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT id, trace_id, analysis_type, confidence,
                       root_causes, systemic_patterns,
                       governance_recommendations,
                       n_failures_analyzed, metadata, created_at
                FROM failure_analysis
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "analyses": [
                    {
                        "id": row[0], "trace_id": row[1],
                        "analysis_type": row[2],
                        "confidence": float(row[3]) if row[3] else 0,
                        "root_causes": json.loads(row[4]) if isinstance(row[4], str) else (row[4] or []),
                        "systemic_patterns": json.loads(row[5]) if isinstance(row[5], str) else (row[5] or []),
                        "recommendations": json.loads(row[6]) if isinstance(row[6], str) else (row[6] or []),
                        "n_failures_analyzed": row[7] or 0,
                        "metadata": json.loads(row[8]) if isinstance(row[8], str) else (row[8] or {}),
                        "created_at": str(row[9]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/mutation-advisory")
async def dashboard_mutation_advisory(limit: int = Query(default=15, le=50)):
    """Phase 19E: Mutation policy trends and advisories."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT id, trace_id, confidence, advisory,
                       exploration_vs_exploitation, entropy_metric,
                       diversification_advisory, metadata, created_at
                FROM mutation_policy_log
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "advisories": [
                    {
                        "id": row[0], "trace_id": row[1],
                        "confidence": float(row[2]) if row[2] else 0,
                        "advisory": row[3],
                        "exploration_vs_exploitation": row[4],
                        "entropy_metric": float(row[5]) if row[5] else 0,
                        "diversification_advisory": row[6],
                        "metadata": json.loads(row[7]) if isinstance(row[7], str) else (row[7] or {}),
                        "created_at": str(row[8]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/scout-synthesis")
async def dashboard_scout_synthesis(limit: int = Query(default=15, le=50)):
    """Phase 19F: Scout consensus/disagreement metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT id, trace_id, confidence, contextual_summary,
                       scout_agreement_score, scout_disagreement_areas,
                       market_state_interpretation, confidence_weights,
                       metadata, created_at
                FROM scout_synthesis_log
                ORDER BY created_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "syntheses": [
                    {
                        "id": row[0], "trace_id": row[1],
                        "confidence": float(row[2]) if row[2] else 0,
                        "summary": row[3],
                        "agreement_score": float(row[4]) if row[4] else 0,
                        "disagreement_areas": json.loads(row[5]) if isinstance(row[5], str) else (row[5] or []),
                        "interpretation": row[6],
                        "confidence_weights": json.loads(row[7]) if isinstance(row[7], str) else (row[7] or {}),
                        "metadata": json.loads(row[8]) if isinstance(row[8], str) else (row[8] or {}),
                        "created_at": str(row[9]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}

# ================================================================
# PHASE 21 — INSTITUTIONAL COPY TRADING ENDPOINTS
# ================================================================

@router.get("/dashboard/api/copy/leader-health")
async def dashboard_leader_health(limit: int = Query(default=20, le=100)):
    """Phase 21E: Leader Health Metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT leader_id, health_score, leader_state,
                       drawdown_pct, survivability_score,
                       execution_quality, replay_consistency,
                       drift_stability, n_followers, assessed_at
                FROM leader_health_metrics
                ORDER BY assessed_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "leaders": [
                    {
                        "leader_id": row[0],
                        "health_score": float(row[1]) if row[1] else 0,
                        "leader_state": row[2],
                        "drawdown_pct": float(row[3]) if row[3] else 0,
                        "survivability_score": float(row[4]) if row[4] else 0,
                        "execution_quality": float(row[5]) if row[5] else 0,
                        "replay_consistency": float(row[6]) if row[6] else 0,
                        "drift_stability": float(row[7]) if row[7] else 0,
                        "n_followers": row[8] or 0,
                        "assessed_at": str(row[9]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/copy/drift")
async def dashboard_copy_drift(limit: int = Query(default=30, le=100)):
    """Phase 21B: Follower Drift Logs."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT leader_id, follower_id, drift_score, drift_severity,
                       exposure_drift, pnl_drift, execution_timing_drift_ms,
                       sync_quality_score, repair_recommendation, detected_at
                FROM copy_drift_log
                ORDER BY detected_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "drifts": [
                    {
                        "leader_id": row[0], "follower_id": row[1],
                        "drift_score": float(row[2]) if row[2] else 0,
                        "drift_severity": row[3],
                        "exposure_drift": float(row[4]) if row[4] else 0,
                        "pnl_drift": float(row[5]) if row[5] else 0,
                        "execution_timing_drift_ms": row[6] or 0,
                        "sync_quality_score": float(row[7]) if row[7] else 0,
                        "repair_recommendation": row[8],
                        "detected_at": str(row[9]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/copy/overlap")
async def dashboard_copy_overlap(limit: int = Query(default=20, le=100)):
    """Phase 21G: Portfolio Overlap Metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT follower_id, overlap_score, concentration_risk,
                       diversification_penalty, duplicated_exposure,
                       n_leaders_analyzed, analyzed_at
                FROM copy_overlap_metrics
                ORDER BY analyzed_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "overlaps": [
                    {
                        "follower_id": row[0],
                        "overlap_score": float(row[1]) if row[1] else 0,
                        "concentration_risk": float(row[2]) if row[2] else 0,
                        "diversification_penalty": float(row[3]) if row[3] else 0,
                        "duplicated_exposure": json.loads(row[4]) if isinstance(row[4], str) else (row[4] or []),
                        "n_leaders_analyzed": row[5] or 0,
                        "analyzed_at": str(row[6]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/copy/quality")
async def dashboard_copy_quality(limit: int = Query(default=20, le=100)):
    """Phase 21J: Copy Performance Analytics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text
            r = await conn.execute(text("""
                SELECT leader_id, follower_id, replication_latency_ms,
                       sync_quality_score, slippage_amplification,
                       execution_divergence, replay_integrity,
                       follower_survivability, measured_at
                FROM copy_quality_metrics
                ORDER BY measured_at DESC LIMIT :limit
            """), {"limit": limit})
            rows = r.fetchall()
            return {
                "count": len(rows),
                "quality_metrics": [
                    {
                        "leader_id": row[0], "follower_id": row[1],
                        "replication_latency_ms": float(row[2]) if row[2] else 0,
                        "sync_quality_score": float(row[3]) if row[3] else 0,
                        "slippage_amplification": float(row[4]) if row[4] else 0,
                        "execution_divergence": float(row[5]) if row[5] else 0,
                        "replay_integrity": float(row[6]) if row[6] else 0,
                        "follower_survivability": float(row[7]) if row[7] else 0,
                        "measured_at": str(row[8]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}
