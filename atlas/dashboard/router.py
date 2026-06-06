"""
Dashboard router â aggregated visibility endpoints for the operator UI.

Endpoints:
  GET /dashboard/              â Serve single-page HTML dashboard
  GET /dashboard/api/overview  â System health + agent + DB stats
  GET /dashboard/api/pipeline  â Strategy lifecycle funnel counts
  GET /dashboard/api/traces    â Recent lifecycle traces
  GET /dashboard/api/patterns  â Pattern intelligence summary
  GET /dashboard/api/risk      â Risk + CopyTrader snapshot
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger
from sqlalchemy import text

from atlas.config.settings import settings

router = APIRouter(tags=["Dashboard"])

_db_client = None
_db_client_lock = asyncio.Lock()


async def _get_db():
    import os
    from atlas.data.storage.timescale_client import TimescaleClient

    global _db_client

    if _db_client is not None:
        return _db_client

    db_url = getattr(settings, "database_url", None) or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set.")

    async with _db_client_lock:
        if _db_client is None:
            db = TimescaleClient(db_url)
            await db.connect()
            # DASHBOARD IS READ-ONLY  no trade seeding, no backtest copying
            _db_client = db
    return _db_client


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
                text("SELECT COUNT(*) FROM paper_trades WHERE status = 'open'")
            )
            open_positions = r.scalar() or 0

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
            active_keys = r.scalar() or 0  # Phase 12 portfolio intelligence stats
            r = await conn.execute(text("SELECT COUNT(*) FROM portfolio_intelligence"))
            portfolio_intel_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM capital_allocation"))
            alloc_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM drift_detection"))
            drift_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM strategy_retirement"))
            retirement_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM execution_realism"))
            realism_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM ensemble_execution"))
            ensemble_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM scout_signals"))
            scout_signals = r.scalar() or 0

            # Phase 11 validation stats
            r = await conn.execute(text("SELECT COUNT(*) FROM walk_forward_analysis"))
            wfa_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM monte_carlo_analysis"))
            mc_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM overfitting_analysis"))
            overfit_count = r.scalar() or 0

            r = await conn.execute(text("SELECT COUNT(*) FROM feature_importance"))
            fi_count = r.scalar() or 0

            r = await conn.execute(
                text("""
                SELECT s.name, br.sharpe, br.win_rate, br.max_drawdown, br.composite_fitness_score
                FROM strategies s
                JOIN backtest_results br ON br.strategy_id = s.id
                WHERE s.status IN ('validated', 'elite') OR s.deployment_mode IN ('paper', 'shadow', 'live')
                ORDER BY br.composite_fitness_score DESC NULLS LAST
                LIMIT 1
            """)
            )
            top_strat = r.fetchone()
            top_strategy_data = (
                {
                    "name": top_strat[0],
                    "sharpe": float(top_strat[1]) if top_strat[1] is not None else None,
                    "win_rate": float(top_strat[2])
                    if top_strat[2] is not None
                    else None,
                    "max_drawdown": float(top_strat[3])
                    if top_strat[3] is not None
                    else None,
                    "fitness": float(top_strat[4])
                    if top_strat[4] is not None
                    else None,
                }
                if top_strat
                else None
            )

            r = await conn.execute(
                text("""
                SELECT s.name, COUNT(pt.id) as trades, COALESCE(SUM(pt.pnl), 0) as total_pnl,
                       SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(pt.id), 0) as win_rate
                FROM paper_trades pt
                JOIN strategies s ON s.id::text = pt.strategy_id::text
                WHERE pt.status IN ('filled', 'closed')
                GROUP BY s.name
                ORDER BY total_pnl DESC
                LIMIT 1
            """)
            )
            top_live = r.fetchone()
            top_live_data = (
                {
                    "name": top_live[0],
                    "trades": top_live[1],
                    "net_return": float(top_live[2]),
                    "win_rate": float(top_live[3]) if top_live[3] is not None else 0.0,
                }
                if top_live
                else None
            )

        # Health check (lightweight â doesn't start API)
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
                "open_positions": open_positions,
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
                "internal_signals": scout_signals,
            },
            "top_strategy": top_strategy_data,
            "top_live": top_live_data,
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
                    if row[4] and hasattr(row[4], "isoformat")
                    else str(row[4])
                    if row[4]
                    else None,
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
                        if row[6] and hasattr(row[6], "isoformat")
                        else str(row[6])
                        if row[6]
                        else None,
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


@router.get("/dashboard/api/validations/list")
async def dashboard_validations_list(limit: int = Query(200, ge=1, le=500)):
    """Phase 30: Detailed validation logs for the dashboard."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            # Fetch strategies that are in validation-related states
            r = await conn.execute(
                text("""
                SELECT s.id, s.name, s.status, s.author_agent, s.created_at,
                       s.validation_metrics, s.compile_error, s.parameters->>'validation_notes' as notes
                FROM strategies s
                WHERE s.status IN ('validated', 'failed_validation', 'backtest_failed', 'code_failed', 'no_signal_strategy')
                ORDER BY s.created_at DESC
                LIMIT :limit
                """),
                {"limit": limit},
            )

            validations = []
            for row in r.fetchall():
                v = dict(row._mapping)
                v["id"] = str(v["id"])
                if hasattr(v["created_at"], "isoformat"):
                    v["created_at"] = v["created_at"].isoformat()

                # Heuristic for "why rejected"
                reason = "Unknown"
                status = v["status"]
                notes = v.get("notes")
                val_metrics = v.get("validation_metrics") or {}

                if status == "validated":
                    reason = "Passed all checks"
                elif status == "failed_validation":
                    if notes:
                        if notes.startswith("{"):  # It's a JSON string of metrics
                            try:
                                nm = json.loads(notes)
                                # Try to extract a human reason
                                if nm.get("tier") == "failed_validation":
                                    reasons = []
                                    if nm.get("test_sharpe", 0) < 0:
                                        reasons.append("Negative Sharpe")
                                    if nm.get("regime_score", 0) < 0.3:
                                        reasons.append("Low Regime Score")
                                    if nm.get("composite_score", 0) < 40:
                                        reasons.append(
                                            f"Low Composite ({nm.get('composite_score', 0)})"
                                        )
                                    reason = (
                                        ", ".join(reasons)
                                        if reasons
                                        else "Criteria not met"
                                    )
                                else:
                                    reason = "Validation criteria not met"
                            except Exception:
                                reason = "Failed validation metrics"
                        elif "|" in notes:
                            reason = notes.split("|")[-1].strip()
                        else:
                            reason = notes
                    else:
                        reason = "Validation criteria not met"
                elif status == "backtest_failed":
                    reason = "Backtest execution error"
                elif status == "code_failed":
                    reason = (
                        v.get("compile_error") or "Syntax/Logic error in generated code"
                    )
                elif status == "no_signal_strategy":
                    reason = "No trade signals generated"

                v["reason"] = reason
                validations.append(v)

        return {"validations": validations}
    except Exception as exc:
        logger.error(f"Dashboard validations list error: {exc}")
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
                LIMIT 50
            """)
            )
            seen = {}
            for row in r.fetchall():
                pattern_type = str(row[1])
                rec = str(row[5]) if row[5] else ""
                key = (pattern_type, rec)
                if key not in seen or float(row[4] or 0) > seen[key]["confidence"]:
                    seen[key] = {
                        "id": str(row[0]),
                        "type": pattern_type,
                        "archetype": str(row[2]) if row[2] else "unknown",
                        "composite_score": float(row[3]) if row[3] else 0.0,
                        "confidence": float(row[4]) if row[4] else 0.0,
                        "recommendation": rec,
                        "detected_at": row[6].isoformat()
                        if row[6] and hasattr(row[6], "isoformat")
                        else str(row[6])
                        if row[6]
                        else None,
                    }

            patterns = sorted(
                seen.values(),
                key=lambda p: (p["confidence"], p["composite_score"]),
                reverse=True,
            )[:20]

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
                {"limit": limit},
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
                    "computed_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
                raw_exposure = float(row[2]) if row[2] else 0
                # Clamp exposure to 0%%-500%% for dashboard sanity
                clamped_exposure = max(0.0, min(5.0, raw_exposure))
                if raw_exposure != clamped_exposure:
                    import logging; logging.warning(f"Exposure clamped: {raw_exposure:.2f} -> {clamped_exposure:.2f} (source data out of bounds)")
                ca = {
                    "computed_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "method": row[1],
                    "total_exposure": clamped_exposure,
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
                ensemble_trades.append(
                    {
                        "executed_at": row[0].isoformat()
                        if hasattr(row[0], "isoformat")
                        else str(row[0]),
                        "signals": row[1],
                        "trades": row[2],
                    }
                )

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
                    "detected_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
                    "analyzed_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
                simulations.append(
                    {
                        "simulated_at": row[0].isoformat()
                        if hasattr(row[0], "isoformat")
                        else str(row[0]),
                        "n_trades": row[1],
                        "fill_prob": float(row[2]) if row[2] else 0,
                        "slippage_bps": float(row[3]) if row[3] else 0,
                        "latency_ms": float(row[4]) if row[4] else 0,
                        "degradation_score": float(row[5]) if row[5] else 0,
                    }
                )
        return {"simulations": simulations}
    except Exception as exc:
        logger.error(f"Dashboard execution realism error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/scouts")
async def dashboard_scouts():
    """Phase 12 Scout Network data â internal scout_signals + external_scout_memory."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            # ââ Internal scout signals (regime, liquidity, correlation, execution scouts) ââ
            r = await conn.execute(
                text("""
                SELECT COALESCE(source, 'unknown') as source, COUNT(*) as cnt
                FROM scout_signals
                GROUP BY source ORDER BY cnt DESC
                """)
            )
            internal_by_source = {str(row[0]): row[1] for row in r.fetchall()}

            r = await conn.execute(
                text("""
                SELECT source, symbol, signal_type, confidence_score,
                       signal_data, created_at
                FROM scout_signals
                ORDER BY created_at DESC LIMIT 20
                """)
            )
            internal_signals = []
            for row in r.fetchall():
                internal_signals.append(
                    {
                        "source": str(row[0]) if row[0] else "unknown",
                        "symbol": str(row[1]) if row[1] else "",
                        "signal_type": str(row[2]) if row[2] else "",
                        "confidence": float(row[3]) if row[3] else 0,
                        "data": str(row[4])[:200] if row[4] else "",
                        "created_at": row[5].isoformat()
                        if hasattr(row[5], "isoformat")
                        else str(row[5]),
                    }
                )

            # ââ External scout signals (Reddit, Discord, YouTube, Podcast) ââ
            external_by_source = {}
            try:
                r = await conn.execute(
                    text("""
                    SELECT source, COUNT(*) as cnt
                    FROM external_scout_memory
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    GROUP BY source ORDER BY cnt DESC
                    """)
                )
                external_by_source = {str(row[0]): row[1] for row in r.fetchall()}
            except Exception:
                pass

            external_signals = []
            try:
                r = await conn.execute(
                    text("""
                    SELECT source, timestamp, sentiment, hypothesis_score,
                           signal_direction, mentioned_tickers
                    FROM external_scout_memory
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    ORDER BY timestamp DESC LIMIT 20
                    """)
                )
                for row in r.fetchall():
                    tickers_raw = row[5]
                    if isinstance(tickers_raw, str):
                        try:
                            tickers_raw = json.loads(tickers_raw)
                        except Exception:
                            tickers_raw = []
                    external_signals.append(
                        {
                            "source": str(row[0]),
                            "timestamp": row[1].isoformat()
                            if hasattr(row[1], "isoformat")
                            else str(row[1]),
                            "sentiment": float(row[2]) if row[2] else 0,
                            "score": float(row[3]) if row[3] else 0,
                            "direction": str(row[4]) if row[4] else "neutral",
                            "mentioned_tickers": tickers_raw,
                        }
                    )
            except Exception:
                pass

            total_all_time = 0
            try:
                r = await conn.execute(text("SELECT COUNT(*) FROM external_scout_memory"))
                total_all_time = r.scalar() or 0
            except Exception:
                pass

        return {
            "internal": {
                "total_signals": sum(internal_by_source.values()),
                "by_source": internal_by_source,
                "recent": internal_signals,
            },
            "external": {
                "total_signals": sum(external_by_source.values()),
                "by_source": external_by_source,
                "recent": external_signals, "total_all_time": total_all_time,
            },
        }
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
                WHERE n_uses >= 3  -- hide features with insufficient sample size
                ORDER BY feature_importance_score DESC
                LIMIT 20
                """)
            )
            features = []
            for row in r.fetchall():
                arch = str(row[4]) if row[4] else ""
                if arch.lower() == "unknown":
                    arch = "Unclassified"
                features.append(
                    {
                        "name": str(row[0]),
                        "importance": float(row[1]) if row[1] else 0,
                        "n_uses": row[2],
                        "survival_rate": float(row[3]) if row[3] else 0,
                        "dominant_archetype": arch,
                        "has_sufficient_data": True,
                    }
                )
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
# PHASE 13 â PRODUCTION GOVERNANCE ENDPOINTS
# ================================================================


@router.get("/dashboard/api/governance/system-health")
async def dashboard_system_health():
    """Phase 13: Latest system health assessment."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT checked_at, composite_score, system_mode, degraded_subsystems, n_degraded
                FROM system_health
                ORDER BY checked_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "checked_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "composite_score": float(row[1]) if row[1] else 0,
                    "system_mode": row[2] or "normal",
                    "degraded_subsystems": row[3]
                    if isinstance(row[3], (list, dict))
                    else [],
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
            r = await conn.execute(
                text("""
                SELECT id, aggregate_type, event_type, aggregate_id, trace_id, created_at
                FROM event_store
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            events = []
            for row in r.fetchall():
                events.append(
                    {
                        "id": str(row[0]),
                        "aggregate_type": row[1],
                        "event_type": row[2],
                        "aggregate_id": row[3],
                        "trace_id": row[4],
                        "created_at": row[5].isoformat()
                        if hasattr(row[5], "isoformat")
                        else str(row[5]),
                    }
                )
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
            r = await conn.execute(
                text("""
                SELECT id, event_type, actor, action, target_id, trace_id, created_at
                FROM audit_ledger
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            entries = []
            for row in r.fetchall():
                entries.append(
                    {
                        "id": str(row[0]),
                        "event_type": row[1],
                        "actor": row[2],
                        "action": row[3],
                        "target_id": row[4],
                        "trace_id": row[5],
                        "created_at": row[6].isoformat()
                        if hasattr(row[6], "isoformat")
                        else str(row[6]),
                    }
                )
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
            r = await conn.execute(
                text("""
                SELECT id, strategy_id, mode, status, approved_by, activated_at
                FROM deployment_governance
                ORDER BY proposed_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            deploys = []
            for row in r.fetchall():
                deploys.append(
                    {
                        "id": str(row[0]),
                        "strategy_id": str(row[1]),
                        "mode": row[2],
                        "status": row[3],
                        "approved_by": row[4],
                        "activated_at": row[5].isoformat()
                        if row[5] and hasattr(row[5], "isoformat")
                        else str(row[5])
                        if row[5]
                        else None,
                    }
                )
            r = await conn.execute(text("SELECT COUNT(*) FROM deployment_governance"))
            total = r.scalar() or 0
        return {"total_deployments": total, "deployments": deploys}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/governance/replay-integrity")
async def dashboard_replay_integrity():
    """Phase 13: Latest replay integrity score."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT checked_at, n_aggregates_checked, integrity_score, n_violations,
                       details
                FROM replay_integrity
                ORDER BY checked_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                details_raw = row[4]
                if isinstance(details_raw, str):
                    try:
                        details_raw = json.loads(details_raw)
                    except Exception:
                        details_raw = {}
                details = details_raw if isinstance(details_raw, dict) else {}
                legacy_violations = details.get("legacy_violations", 0)
                active_violations = details.get("active_violations", 0)
                return {
                    "checked_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "n_aggregates": row[1] or 0,
                    "integrity_score": float(row[2]) if row[2] else 0,
                    "n_violations": row[3] or 0,
                    "legacy_violations": legacy_violations,
                    "active_violations": active_violations,
                }
            return {"message": "No replay integrity data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 14 â PORTFOLIO DURABILITY ENDPOINTS
# ================================================================


@router.get("/dashboard/api/risk/systemic")
async def dashboard_systemic_risk():
    """Phase 14: Latest systemic risk assessment."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT assessed_at, systemic_risk_score, contagion_probability, portfolio_fragility
                FROM systemic_risk
                ORDER BY assessed_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "assessed_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
            r = await conn.execute(
                text("""
                SELECT tested_at, n_scenarios, worst_scenario, min_survival_probability, max_drawdown
                FROM stress_test_results
                ORDER BY tested_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "tested_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
            r = await conn.execute(
                text("""
                SELECT checked_at, drawdown_pct, action_taken, total_exposure
                FROM capital_preservation_state
                ORDER BY checked_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "checked_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
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
            r = await conn.execute(
                text("""
                SELECT optimized_at, method_used, n_strategies
                FROM advanced_portfolio_optimization
                ORDER BY optimized_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "optimized_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "method": row[1] or "",
                    "n_strategies": row[2] or 0,
                }
            return {"message": "No optimizer data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 15 â META-LEARNING ENDPOINTS
# ================================================================


@router.get("/dashboard/api/meta/prompts")
async def dashboard_prompts(limit: int = 20):
    """Phase 15: Prompt evolution templates."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT id, prompt_type, archetype, status, effectiveness_score, generation_count
                FROM prompt_templates
                ORDER BY effectiveness_score DESC
                LIMIT :limit
            """),
                {"limit": limit},
            )
            prompts = []
            for row in r.fetchall():
                prompts.append(
                    {
                        "id": str(row[0]),
                        "type": row[1],
                        "archetype": row[2],
                        "status": row[3],
                        "effectiveness": float(row[4]) if row[4] else 0,
                        "generations": row[5] or 0,
                    }
                )
        return {"prompts": prompts}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/mutation-policy")
async def dashboard_mutation_policy():
    """Phase 15: Latest mutation policy state."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT learned_at, n_observations
                FROM mutation_policy_state
                ORDER BY learned_at DESC LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "learned_at": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "n_observations": row[1] or 0,
                }
            return {"message": "No mutation policy data"}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 17 â OBSERVABILITY ENDPOINTS
# ================================================================


@router.get("/dashboard/api/observability/metrics")
async def dashboard_metrics(limit: int = 20):
    """Phase 17: Monitoring fabric metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT recorded_at, counters, latencies
                FROM monitoring_metrics
                ORDER BY recorded_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            metrics = []
            for row in r.fetchall():
                metrics.append(
                    {
                        "recorded_at": row[0].isoformat()
                        if hasattr(row[0], "isoformat")
                        else str(row[0]),
                        "counters": row[1] if isinstance(row[1], dict) else {},
                    }
                )
        return {"metrics": metrics}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/observability/anomalies")
async def dashboard_anomalies(limit: int = 20):
    """Phase 17: Anomaly observations."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT observed_at, n_anomalies, severity
                FROM anomaly_observations
                ORDER BY observed_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            anomalies = []
            for row in r.fetchall():
                anomalies.append(
                    {
                        "observed_at": row[0].isoformat()
                        if hasattr(row[0], "isoformat")
                        else str(row[0]),
                        "n_anomalies": row[1] or 0,
                        "severity": float(row[2]) if row[2] else 0,
                    }
                )
        return {"anomalies": anomalies}
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 18 â DASHBOARD OVERVIEW ENHANCEMENT
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
# TRADES â Real paper trades with strategy linkage
# ================================================================


@router.get("/dashboard/api/trades")
async def dashboard_trades(limit: int = Query(default=50, ge=1, le=200)):
    """Recent paper trades with strategy name linkage."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT
                    pt.id, pt.time, pt.strategy_id, pt.symbol,
                    pt.side, pt.quantity, pt.price, pt.fill_price,
                    pt.status, pt.pnl, s.name AS strategy_name
                FROM paper_trades pt
                LEFT JOIN strategies s ON s.id::text = pt.strategy_id::text
                ORDER BY pt.time DESC
                LIMIT :limit
                """),
                {"limit": limit},
            )
            trades = []
            for row in r.fetchall():
                t = dict(row._mapping)
                t["id"] = str(t["id"]) if t.get("id") else None
                t["strategy_id"] = (
                    str(t["strategy_id"]) if t.get("strategy_id") else None
                )
                if hasattr(t.get("time"), "isoformat"):
                    t["time"] = t["time"].isoformat()
                trades.append(t)

            r = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
            total = r.scalar() or 0

            r = await conn.execute(
                text(
                    "SELECT COALESCE(SUM(pnl), 0) FROM paper_trades WHERE status = 'filled'"
                )
            )
            total_pnl = float(r.scalar() or 0.0)

            r = await conn.execute(
                text(
                    "SELECT COUNT(DISTINCT strategy_id) FROM paper_trades WHERE strategy_id IS NOT NULL"
                )
            )
            strategies_with_trades = r.scalar() or 0

        return {
            "total_trades": total,
            "total_pnl": total_pnl,
            "strategies_with_trades": strategies_with_trades,
            "trades": trades,
        }
    except Exception as exc:
        logger.error(f"Dashboard trades error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/trades/by-strategy/{strategy_id}")
async def dashboard_trades_by_strategy(strategy_id: str):
    """Paper trades for a specific strategy."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT
                    pt.id, pt.time, pt.symbol,
                    pt.side, pt.quantity, pt.price, pt.fill_price,
                    pt.status, pt.pnl, s.name AS strategy_name
                FROM paper_trades pt
                LEFT JOIN strategies s ON s.id::text = pt.strategy_id::text
                WHERE pt.strategy_id::text = :sid
                ORDER BY pt.time DESC
                """),
                {"sid": strategy_id},
            )
            trades = []
            for row in r.fetchall():
                t = dict(row._mapping)
                t["id"] = str(t["id"]) if t.get("id") else None
                t["time"] = (
                    t["time"].isoformat()
                    if hasattr(t["time"], "isoformat")
                    else str(t["time"])
                )
                trades.append(t)

        return {
            "strategy_id": strategy_id,
            "count": len(trades),
            "trades": trades,
        }
    except Exception as exc:
        logger.error(f"Dashboard trades by strategy error: {exc}")
        return {"error": str(exc)}


# ================================================================
# STRATEGY REGISTRY â All strategies with backtest + lifecycle
# ================================================================


@router.get("/dashboard/api/strategies")
async def dashboard_strategies_list(limit: int = Query(default=100, ge=1, le=500)):
    """List all strategies with latest backtest results and lifecycle state."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT
                    s.id, s.name, s.status, s.author_agent, s.lifecycle_state,
                    s.mutation_type, s.trace_id, s.created_at,
                    br.sharpe, br.win_rate, br.total_trades,
                    br.composite_fitness_score, br.sortino_ratio,
                    br.max_drawdown, br.expectancy
                FROM strategies s
                LEFT JOIN LATERAL (
                    SELECT sharpe, win_rate, total_trades,
                           composite_fitness_score, sortino_ratio,
                           max_drawdown, expectancy
                    FROM backtest_results
                    WHERE strategy_id = s.id
                    ORDER BY created_at DESC LIMIT 1
                ) br ON TRUE
                ORDER BY s.created_at DESC
                LIMIT :limit
                """),
                {"limit": limit},
            )
            strategies = []
            for row in r.fetchall():
                strategies.append(
                    {
                        "id": str(row[0]),
                        "name": row[1],
                        "status": row[2],
                        "author": row[3],
                        "lifecycle_state": row[4],
                        "mutation_type": row[5],
                        "trace_id": str(row[6]) if row[6] else None,
                        "created_at": str(row[7]) if row[7] else "",
                        "backtest": {
                            "sharpe": float(row[8]) if row[8] is not None else None,
                            "win_rate": float(row[9]) if row[9] is not None else None,
                            "total_trades": row[10],
                            "fitness": float(row[11]) if row[11] is not None else None,
                            "sortino": float(row[12]) if row[12] is not None else None,
                            "max_drawdown": float(row[13])
                            if row[13] is not None
                            else None,
                            "expectancy": float(row[14])
                            if row[14] is not None
                            else None,
                        }
                        if any(v is not None for v in row[8:15])
                        else None,
                    }
                )

            r = await conn.execute(
                text("""
                SELECT status, COUNT(*) as cnt
                FROM strategies GROUP BY status ORDER BY cnt DESC
            """)
            )
            status_counts = {str(row[0]): row[1] for row in r.fetchall()}

            r = await conn.execute(text("SELECT COUNT(*) FROM strategies"))
            total = r.scalar() or 0

        return {
            "total": total,
            "status_counts": status_counts,
            "strategies": strategies,
        }
    except Exception as exc:
        logger.error(f"Dashboard strategies list error: {exc}")
        return {"error": str(exc)}


# ================================================================
# AGENT REGISTRY â All agents with status, last run, health
# ================================================================


@router.get("/dashboard/api/agents")
async def dashboard_agents_list(limit: int = Query(default=50, ge=1, le=200)):
    """List all known agents with governance scores and recent activity."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            agents = []

            # From agent_governance_state
            r = await conn.execute(
                text("""
                SELECT assessed_at, n_agents_assessed, agent_scores, throttled_agents
                FROM agent_governance_state
                ORDER BY assessed_at DESC LIMIT 1
                """)
            )
            gov_row = r.fetchone()
            governance = None
            if gov_row:
                governance = {
                    "assessed_at": str(gov_row[0]) if gov_row[0] else "",
                    "n_agents_assessed": gov_row[1] or 0,
                    "agent_scores": gov_row[2] if isinstance(gov_row[2], dict) else {},
                    "throttled_agents": gov_row[3]
                    if isinstance(gov_row[3], list)
                    else [],
                }

            # Distinct author_agents from strategies table as agent registry
            r = await conn.execute(
                text("""
                SELECT
                    author_agent,
                    COUNT(*) as strategy_count,
                    COUNT(*) FILTER (WHERE status = 'validated') as validated_count,
                    MAX(created_at) as last_active
                FROM strategies
                WHERE author_agent IS NOT NULL
                GROUP BY author_agent
                ORDER BY last_active DESC
                LIMIT :limit
                """),
                {"limit": limit},
            )
            for row in r.fetchall():
                agents.append(
                    {
                        "name": row[0],
                        "strategy_count": row[1],
                        "validated_count": row[2],
                        "last_active": str(row[3]) if row[3] else "",
                    }
                )

            # From lifecycle_events for recent actor activity
            r = await conn.execute(
                text("""
                SELECT actor, COUNT(*) as event_count, MAX(created_at) as last_seen
                FROM lifecycle_events
                WHERE actor IS NOT NULL
                GROUP BY actor
                ORDER BY last_seen DESC
                LIMIT :limit
                """),
                {"limit": limit},
            )
            actor_map = {}
            for row in r.fetchall():
                actor_map[row[0]] = {
                    "event_count": row[1],
                    "last_seen": str(row[2]) if row[2] else "",
                }

            # Merge actor activity into agents
            for a in agents:
                act = actor_map.get(a["name"], {})
                a["event_count"] = act.get("event_count", 0)
                a["last_seen"] = act.get("last_seen", a["last_active"])

        return {
            "agents": agents,
            "governance": governance,
        }
    except Exception as exc:
        logger.error(f"Dashboard agents list error: {exc}")
        return {"error": str(exc)}




@router.get("/dashboard/api/agents/live")
async def dashboard_agents_live():
    """Read live agent statuses from Redis heartbeats."""
    try:
        from redis.asyncio import Redis
        from atlas.config.settings import get_settings as get_stg
        stg = get_stg()
        redis_client = Redis.from_url(stg.redis_url)
        try:
            cursor = 0
            live_agents = []
            while True:
                cursor, keys = await redis_client.scan(cursor=cursor, match="agent:*", count=100)
                for key in keys:
                    data = await redis_client.hgetall(key)
                    if data:
                        agent_id = key.decode() if isinstance(key, bytes) else key
                        agent_id = agent_id.replace("agent:", "", 1)
                        decoded = {}
                        for k, v in data.items():
                            k_str = k.decode() if isinstance(k, bytes) else k
                            v_str = v.decode() if isinstance(v, bytes) else v
                            decoded[k_str] = v_str
                        live_agents.append({
                            "agent_id": agent_id,
                            "name": decoded.get("name", "unknown"),
                            "type": decoded.get("agent_type", ""),
                            "layer": decoded.get("layer", ""),
                            "status": decoded.get("status", "stopped"),
                            "advisory_only": decoded.get("advisory_only", "false"),
                        })
                if cursor == 0:
                    break
            return {"agents": live_agents, "count": len(live_agents)}
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass
    except Exception as exc:
        logger.error(f"Dashboard live agents error: {exc}")
        return {"error": str(exc), "agents": [], "count": 0}

# ================================================================
# STRATEGY DETAIL â Full strategy with validation reasons + trades
# ================================================================


@router.get("/dashboard/api/strategies/{strategy_id}")
async def dashboard_strategy_detail(strategy_id: str):
    """Full strategy detail: metadata, backtest results, all validation scores, and trades."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            # 1. Strategy metadata
            r = await conn.execute(
                text("""
                SELECT id, name, status, author_agent, strategy_signature,
                       mutation_type, lifecycle_state, age_bars,
                       compile_error, trace_id, generation_batch,
                       created_at, code, parameters, prompt
                FROM strategies
                WHERE id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            if not row:
                return {"error": f"Strategy {strategy_id} not found"}

            params_raw = row[13]
            if isinstance(params_raw, str):
                try:
                    params_parsed = json.loads(params_raw)
                except Exception:
                    params_parsed = {}
            else:
                params_parsed = params_raw or {}

            strategy = {
                "id": str(row[0]),
                "name": row[1],
                "status": row[2],
                "author": row[3],
                "signature": row[4],
                "mutation_type": row[5],
                "lifecycle_state": row[6],
                "age_bars": row[7],
                "compile_error": row[8],
                "trace_id": row[9],
                "generation_batch": row[10],
                "created_at": str(row[11]) if row[11] else "",
                "code": row[12],
                "parameters": params_parsed,
                "prompt": row[14],
            }

            # 2. Backtest results
            r = await conn.execute(
                text("""
                SELECT sharpe, win_rate, total_trades, composite_fitness_score,
                       sortino_ratio, calmar_ratio, expectancy, created_at
                FROM backtest_results
                WHERE strategy_id = :sid
                ORDER BY created_at DESC LIMIT 1
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            backtest = None
            if row:
                backtest = {
                    "sharpe": float(row[0]) if row[0] else None,
                    "win_rate": float(row[1]) if row[1] else None,
                    "total_trades": row[2],
                    "composite_fitness": float(row[3]) if row[3] else None,
                    "sortino": float(row[4]) if row[4] else None,
                    "calmar": float(row[5]) if row[5] else None,
                    "expectancy": float(row[6]) if row[6] else None,
                    "created_at": str(row[7]) if row[7] else "",
                }

            # 3. Walk-forward validation
            r = await conn.execute(
                text("""
                SELECT walk_forward_score, temporal_consistency, regime_survival_score,
                       n_windows_survived, n_windows_total, analyzed_at
                FROM walk_forward_analysis
                WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            walk_forward = None
            if row:
                walk_forward = {
                    "walk_forward_score": float(row[0]) if row[0] else None,
                    "temporal_consistency": float(row[1]) if row[1] else None,
                    "regime_survival_score": float(row[2]) if row[2] else None,
                    "n_windows_survived": row[3],
                    "n_windows_total": row[4],
                    "analyzed_at": str(row[5]) if row[5] else "",
                }

            # 4. Monte Carlo validation
            r = await conn.execute(
                text("""
                SELECT monte_carlo_survival_score, expected_tail_drawdown,
                       probabilistic_sharpe, n_simulations, simulated_at
                FROM monte_carlo_analysis
                WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            monte_carlo = None
            if row:
                monte_carlo = {
                    "survival_score": float(row[0]) if row[0] else None,
                    "tail_drawdown": float(row[1]) if row[1] else None,
                    "prob_sharpe": float(row[2]) if row[2] else None,
                    "n_simulations": row[3],
                    "simulated_at": str(row[4]) if row[4] else "",
                }

            # 5. Overfitting analysis
            r = await conn.execute(
                text("""
                SELECT overfit_probability, robustness_score,
                       parameter_stability_score, analyzed_at
                FROM overfitting_analysis
                WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            overfitting = None
            if row:
                overfitting = {
                    "overfit_probability": float(row[0]) if row[0] else None,
                    "robustness_score": float(row[1]) if row[1] else None,
                    "stability_score": float(row[2]) if row[2] else None,
                    "analyzed_at": str(row[3]) if row[3] else "",
                }

            # 6. Regime validation
            r = await conn.execute(
                text("""
                SELECT regime_survival_score, regime_dependency_score,
                       n_regimes_survived, over_specialized, validated_at
                FROM regime_validation
                WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            regime_val = None
            if row:
                regime_val = {
                    "survival_score": float(row[0]) if row[0] else None,
                    "dependency_score": float(row[1]) if row[1] else None,
                    "n_regimes": row[2],
                    "over_specialized": bool(row[3]) if row[3] else False,
                    "validated_at": str(row[4]) if row[4] else "",
                }

            # 7. Cost stress test
            r = await conn.execute(
                text("""
                SELECT cost_survival_score, max_survivable_multiplier,
                       passes_min_survival, fragile_scalper_detected, tested_at
                FROM cost_stress_analysis
                WHERE strategy_id = :sid
                """),
                {"sid": strategy_id},
            )
            row = r.fetchone()
            cost_stress = None
            if row:
                cost_stress = {
                    "survival_score": float(row[0]) if row[0] else None,
                    "max_multiplier": float(row[1]) if row[1] else None,
                    "passes_min_survival": bool(row[2]) if row[2] else False,
                    "fragile_scalper": bool(row[3]) if row[3] else False,
                    "tested_at": str(row[4]) if row[4] else "",
                }

            # 8. Lifecycle events (traces) for this strategy
            r = await conn.execute(
                text("""
                SELECT trace_id, stage, status, actor, created_at
                FROM lifecycle_events
                WHERE strategy_id = :sid
                ORDER BY created_at DESC LIMIT 20
                """),
                {"sid": strategy_id},
            )
            lifecycle_traces = []
            for row in r.fetchall():
                lifecycle_traces.append(
                    {
                        "trace_id": str(row[0]),
                        "stage": row[1],
                        "status": row[2],
                        "actor": row[3],
                        "created_at": str(row[4]) if row[4] else "",
                    }
                )

        # Compile validation pass/fail reasons
        validation_reasons = []
        if walk_forward:
            wf_score = walk_forward.get("walk_forward_score")
            if wf_score is not None and wf_score >= 60:
                validation_reasons.append(
                    {
                        "check": "walk_forward",
                        "passed": True,
                        "detail": f"Score {wf_score:.1f}/100",
                    }
                )
            elif wf_score is not None:
                validation_reasons.append(
                    {
                        "check": "walk_forward",
                        "passed": False,
                        "detail": f"Score {wf_score:.1f}/100 â below 60 threshold",
                    }
                )

        if monte_carlo:
            mc_score = monte_carlo.get("survival_score")
            if mc_score is not None and mc_score >= 50:
                validation_reasons.append(
                    {
                        "check": "monte_carlo",
                        "passed": True,
                        "detail": f"Survival {mc_score:.1f}%, Sharpe {monte_carlo.get('prob_sharpe', 'N/A')}",
                    }
                )
            elif mc_score is not None:
                validation_reasons.append(
                    {
                        "check": "monte_carlo",
                        "passed": False,
                        "detail": f"Survival {mc_score:.1f}% â below 50% threshold",
                    }
                )

        if overfitting:
            of_prob = overfitting.get("overfit_probability")
            if of_prob is not None and of_prob < 50:
                validation_reasons.append(
                    {
                        "check": "overfitting",
                        "passed": True,
                        "detail": f"Overfit probability {of_prob:.1f}% â low risk",
                    }
                )
            elif of_prob is not None:
                validation_reasons.append(
                    {
                        "check": "overfitting",
                        "passed": False,
                        "detail": f"Overfit probability {of_prob:.1f}% â high risk",
                    }
                )

        if regime_val:
            rs = regime_val.get("survival_score")
            if rs is not None and rs >= 50:
                validation_reasons.append(
                    {
                        "check": "regime_resilience",
                        "passed": True,
                        "detail": f"Survived {regime_val.get('n_regimes', 0)} regimes, score {rs:.1f}",
                    }
                )
            elif rs is not None:
                validation_reasons.append(
                    {
                        "check": "regime_resilience",
                        "passed": False,
                        "detail": f"Regime score {rs:.1f}, over-specialized={regime_val.get('over_specialized', False)}",
                    }
                )

        if cost_stress:
            cs_score = cost_stress.get("survival_score")
            if cs_score is not None and cost_stress.get("passes_min_survival", False):
                validation_reasons.append(
                    {
                        "check": "cost_stress",
                        "passed": True,
                        "detail": f"Survival score {cs_score:.1f}, max multiplier {cost_stress.get('max_multiplier', 'N/A')}x",
                    }
                )
            elif cs_score is not None:
                validation_reasons.append(
                    {
                        "check": "cost_stress",
                        "passed": False,
                        "detail": f"Score {cs_score:.1f}, fragile_scalper={cost_stress.get('fragile_scalper', False)}",
                    }
                )

        return {
            "strategy": strategy,
            "backtest": backtest,
            "validation": {
                "walk_forward": walk_forward,
                "monte_carlo": monte_carlo,
                "overfitting": overfitting,
                "regime": regime_val,
                "cost_stress": cost_stress,
            },
            "validation_reasons": validation_reasons,
            "lifecycle_traces": lifecycle_traces,
        }
    except Exception as exc:
        logger.error(f"Dashboard strategy detail error: {exc}")
        return {"error": str(exc)}


# ================================================================
# PHASE 19 â META-INTELLIGENCE DASHBOARD ENDPOINTS
# ================================================================


@router.get("/dashboard/api/meta-reasoning")
async def dashboard_meta_reasoning(limit: int = Query(default=20, le=100)):
    """Phase 19B: Latest MetaReasoningAgent advisories."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT id, trace_id, advisory_type, confidence,
                       reasoning_text, recommendations,
                       metadata, created_at
                FROM meta_reasoning_log
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "advisories": [
                    {
                        "id": row[0],
                        "trace_id": row[1],
                        "advisory_type": row[2],
                        "confidence": float(row[3]) if row[3] else 0,
                        "reasoning": row[4],
                        "recommendations": json.loads(row[5])
                        if isinstance(row[5], str)
                        else (row[5] or []),
                        "metadata": json.loads(row[6])
                        if isinstance(row[6], str)
                        else (row[6] or {}),
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
                r = await conn.execute(
                    text("""
                    SELECT id, trace_id, statement, observation_source,
                           confidence, evidence_count, contradiction_count,
                           status, regime_scope, decay_rate,
                           created_at, updated_at
                    FROM hypothesis_registry
                    WHERE status = :status
                    ORDER BY confidence DESC LIMIT :limit
                """),
                    {"status": status, "limit": limit},
                )
            else:
                r = await conn.execute(
                    text("""
                    SELECT id, trace_id, statement, observation_source,
                           confidence, evidence_count, contradiction_count,
                           status, regime_scope, decay_rate,
                           created_at, updated_at
                    FROM hypothesis_registry
                    ORDER BY created_at DESC LIMIT :limit
                """),
                    {"limit": limit},
                )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "hypotheses": [
                    {
                        "id": row[0],
                        "trace_id": row[1],
                        "statement": row[2],
                        "source": row[3],
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

            r = await conn.execute(
                text("""
                SELECT id, trace_id, analysis_type, confidence,
                       root_causes, systemic_patterns,
                       governance_recommendations,
                       n_failures_analyzed, metadata, created_at
                FROM failure_analysis
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "analyses": [
                    {
                        "id": row[0],
                        "trace_id": row[1],
                        "analysis_type": row[2],
                        "confidence": float(row[3]) if row[3] else 0,
                        "root_causes": json.loads(row[4])
                        if isinstance(row[4], str)
                        else (row[4] or []),
                        "systemic_patterns": json.loads(row[5])
                        if isinstance(row[5], str)
                        else (row[5] or []),
                        "recommendations": json.loads(row[6])
                        if isinstance(row[6], str)
                        else (row[6] or []),
                        "n_failures_analyzed": row[7] or 0,
                        "metadata": json.loads(row[8])
                        if isinstance(row[8], str)
                        else (row[8] or {}),
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

            r = await conn.execute(
                text("""
                SELECT id, trace_id, confidence, advisory,
                       exploration_vs_exploitation, entropy_metric,
                       diversification_advisory, metadata, created_at
                FROM mutation_policy_log
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "advisories": [
                    {
                        "id": row[0],
                        "trace_id": row[1],
                        "confidence": float(row[2]) if row[2] else 0,
                        "advisory": row[3],
                        "exploration_vs_exploitation": row[4],
                        "entropy_metric": float(row[5]) if row[5] else 0,
                        "diversification_advisory": row[6],
                        "metadata": json.loads(row[7])
                        if isinstance(row[7], str)
                        else (row[7] or {}),
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

            r = await conn.execute(
                text("""
                SELECT id, trace_id, confidence, contextual_summary,
                       scout_agreement_score, scout_disagreement_areas,
                       market_state_interpretation, confidence_weights,
                       metadata, created_at
                FROM scout_synthesis_log
                ORDER BY created_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "syntheses": [
                    {
                        "id": row[0],
                        "trace_id": row[1],
                        "confidence": float(row[2]) if row[2] else 0,
                        "summary": row[3],
                        "agreement_score": float(row[4]) if row[4] else 0,
                        "disagreement_areas": json.loads(row[5])
                        if isinstance(row[5], str)
                        else (row[5] or []),
                        "interpretation": row[6],
                        "confidence_weights": json.loads(row[7])
                        if isinstance(row[7], str)
                        else (row[7] or {}),
                        "metadata": json.loads(row[8])
                        if isinstance(row[8], str)
                        else (row[8] or {}),
                        "created_at": str(row[9]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 21 â INSTITUTIONAL COPY TRADING ENDPOINTS
# ================================================================


@router.get("/dashboard/api/copy/leader-health")
async def dashboard_leader_health(limit: int = Query(default=20, le=100)):
    """Phase 21E: Leader Health Metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT leader_id, health_score, leader_state,
                       drawdown_pct, survivability_score,
                       execution_quality, replay_consistency,
                       drift_stability, n_followers, assessed_at
                FROM leader_health_metrics
                ORDER BY assessed_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
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

            r = await conn.execute(
                text("""
                SELECT leader_id, follower_id, drift_score, drift_severity,
                       exposure_drift, pnl_drift, execution_timing_drift_ms,
                       sync_quality_score, repair_recommendation, detected_at
                FROM copy_drift_log
                ORDER BY detected_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "drifts": [
                    {
                        "leader_id": row[0],
                        "follower_id": row[1],
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

            r = await conn.execute(
                text("""
                SELECT follower_id, overlap_score, concentration_risk,
                       diversification_penalty, duplicated_exposure,
                       n_leaders_analyzed, analyzed_at
                FROM copy_overlap_metrics
                ORDER BY analyzed_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "overlaps": [
                    {
                        "follower_id": row[0],
                        "overlap_score": float(row[1]) if row[1] else 0,
                        "concentration_risk": float(row[2]) if row[2] else 0,
                        "diversification_penalty": float(row[3]) if row[3] else 0,
                        "duplicated_exposure": json.loads(row[4])
                        if isinstance(row[4], str)
                        else (row[4] or []),
                        "n_leaders_analyzed": row[5] or 0,
                        "analyzed_at": str(row[6]),
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


# ================================================================
# PHASE 32/33 â ADAPTIVE INTELLIGENCE & BENCHMARK ENDPOINTS
# ================================================================


@router.get("/dashboard/api/meta/agent-governance")
async def dashboard_agent_governance():
    """Phase 15: Agent reliability and performance governance."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                SELECT assessed_at, n_agents_assessed, agent_scores, throttled_agents
                FROM agent_governance_state
                ORDER BY assessed_at DESC
                LIMIT 1
            """)
            )
            row = r.fetchone()
            if row:
                return {
                    "assessed_at": str(row[0]),
                    "n_agents_assessed": row[1],
                    "agent_scores": row[2],
                    "throttled_agents": row[3],
                }
            return {
                "n_agents_assessed": 0,
                "agent_scores": {},
                "throttled_agents": [],
            }
    except Exception as exc:
        logger.error(f"Dashboard agent governance error: {exc}")
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/mutation-families")
async def dashboard_mutation_families(limit: int = Query(default=20, le=100)):
    """Phase 32: Mutation family performance rankings."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT family_id, family_name, n_members,
                       avg_fitness, best_fitness, survival_rate,
                       dominant_archetype, lineage_depth, last_active
                FROM mutation_families
                ORDER BY avg_fitness DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "families": [
                    {
                        "family_id": str(row[0]),
                        "family_name": row[1],
                        "n_members": row[2] or 0,
                        "avg_fitness": float(row[3]) if row[3] else 0,
                        "best_fitness": float(row[4]) if row[4] else 0,
                        "survival_rate": float(row[5]) if row[5] else 0,
                        "dominant_archetype": row[6] or "mixed",
                        "lineage_depth": row[7] or 0,
                        "last_active": str(row[8]) if row[8] else "",
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/dominant-organisms")
async def dashboard_dominant_organisms(limit: int = Query(default=20, le=100)):
    """Phase 32: Dominant organism emergence tracking."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT strategy_id, strategy_name, archetype,
                       fitness_score, dominance_duration_hours,
                       n_generations_dominant, specialization_regime,
                       last_detected_at
                FROM dominant_organisms
                ORDER BY fitness_score DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            if rows:
                return {
                    "count": len(rows),
                    "organisms": [
                        {
                            "strategy_id": str(row[0]),
                            "strategy_name": row[1],
                            "archetype": row[2] or "unknown",
                            "fitness_score": float(row[3]) if row[3] else 0,
                            "dominance_hours": float(row[4]) if row[4] else 0,
                            "generations": row[5] or 0,
                            "regime": row[6] or "all",
                            "last_detected": str(row[7]) if row[7] else "",
                        }
                        for row in rows
                    ],
                }
            return {
                "count": 0,
                "organisms": [],
                "message": "No dominant organisms yet (requires longer runtime)",
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/regime-specialization")
async def dashboard_regime_specialization(limit: int = Query(default=20, le=100)):
    """Phase 32: Regime specialization profiles."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT strategy_id, profiled_at, bull, bear,
                       ranging, high_vol, low_vol, archetype
                FROM regime_specialization
                ORDER BY profiled_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "profiles": [
                    {
                        "strategy_id": str(row[0]),
                        "profiled_at": str(row[1]),
                        "bull": float(row[2]) if row[2] else 0,
                        "bear": float(row[3]) if row[3] else 0,
                        "ranging": float(row[4]) if row[4] else 0,
                        "high_vol": float(row[5]) if row[5] else 0,
                        "low_vol": float(row[6]) if row[6] else 0,
                        "archetype": row[7] or "generalist",
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/scout-rankings")
async def dashboard_scout_rankings(limit: int = Query(default=20, le=100)):
    """Phase 32: Scout predictive rankings."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT source_scout, prediction_accuracy,
                       signal_quality_score, divergence_score,
                       n_predictions, trust_score, ranked_at
                FROM scout_predictive_rankings
                ORDER BY prediction_accuracy DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "rankings": [
                    {
                        "scout_name": row[0],
                        "prediction_accuracy": float(row[1]) if row[1] else 0,
                        "signal_quality": float(row[2]) if row[2] else 0,
                        "divergence_score": float(row[3]) if row[3] else 0,
                        "n_predictions": row[4] or 0,
                        "trust_score": float(row[5]) if row[5] else 0,
                        "ranked_at": str(row[6]) if row[6] else "",
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/portfolio-evolution")
async def dashboard_portfolio_evolution(limit: int = Query(default=20, le=100)):
    """Phase 32: Portfolio evolution and capital migration tracking."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT tracked_at, diversification_score,
                       correlation_collapse_risk, contagion_exposure,
                       concentration_risk, portfolio_survivability,
                       capital_migrated, weak_penalized, dominant_boosted
                FROM portfolio_evolution_log
                ORDER BY tracked_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "evolution": [
                    {
                        "tracked_at": str(row[0]),
                        "diversification_score": float(row[1]) if row[1] else 0,
                        "collapse_risk": float(row[2]) if row[2] else 0,
                        "contagion_exposure": float(row[3]) if row[3] else 0,
                        "concentration_risk": float(row[4]) if row[4] else 0,
                        "survivability": float(row[5]) if row[5] else 0,
                        "capital_migrated": float(row[6]) if row[6] else 0,
                        "weak_penalized": row[7] or 0,
                        "dominant_boosted": row[8] or 0,
                    }
                    for row in rows
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/dashboard/api/meta/adaptive-intelligence")
async def dashboard_adaptive_intelligence(limit: int = Query(default=50, le=200)):
    """Phase 33: Adaptive intelligence benchmark metrics."""
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            from sqlalchemy.sql import text

            r = await conn.execute(
                text("""
                SELECT recorded_at, runtime_minutes,
                       adaptive_quality_score, specialization_quality_score,
                       allocation_quality_score, evolutionary_selection_score,
                       long_horizon_survivability_score,
                       recovery_quality, drawdown_resilience, diversification_quality,
                       replay_integrity, execution_degradation,
                       dominant_organisms, active_organisms
                FROM phase33_performance_metrics
                ORDER BY recorded_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "metrics": [
                    {
                        "recorded_at": str(row[0]),
                        "runtime_minutes": row[1] or 0,
                        "adaptive_quality": float(row[2]) if row[2] else 0,
                        "specialization_quality": float(row[3]) if row[3] else 0,
                        "allocation_quality": float(row[4]) if row[4] else 0,
                        "evolutionary_selection": float(row[5]) if row[5] else 0,
                        "long_horizon_survivability": float(row[6]) if row[6] else 0,
                        "recovery_quality": float(row[7]) if row[7] else 0,
                        "drawdown_resilience": float(row[8]) if row[8] else 0,
                        "diversification_quality": float(row[9]) if row[9] else 0,
                        "replay_integrity": float(row[10]) if row[10] else 0,
                        "execution_degradation": float(row[11]) if row[11] else 0,
                        "dominant_organisms": row[12] or 0,
                        "active_organisms": row[13] or 0,
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

            r = await conn.execute(
                text("""
                SELECT leader_id, follower_id, replication_latency_ms,
                       sync_quality_score, slippage_amplification,
                       execution_divergence, replay_integrity,
                       follower_survivability, measured_at
                FROM copy_quality_metrics
                ORDER BY measured_at DESC LIMIT :limit
            """),
                {"limit": limit},
            )
            rows = r.fetchall()
            return {
                "count": len(rows),
                "quality_metrics": [
                    {
                        "leader_id": row[0],
                        "follower_id": row[1],
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
# ================================================================
# REGRESSION DETECTION — Strategy health monitoring
# ================================================================


@router.get("/dashboard/api/governance/regression")
async def dashboard_regression(limit: int = Query(default=50, ge=1, le=200)):
    """
    Regression detection status and rollback history.

    For each deployed strategy, queries the 4 advanced validation tables
    (walk_forward, overfitting, regime, Monte Carlo) to compute a
    multi-dimensional regression signal count (0-4). Also returns
    rollback history from deployment_governance.

    A strategy is flagged as regressed if 2+ of 4 signals fire.
    """
    try:
        db = await _get_db()
        async with db.engine.connect() as conn:
            # 1. All deployments with their current regression status
            r = await conn.execute(
                text("""
                    SELECT
                        d.id AS deployment_id,
                        d.strategy_id,
                        s.name AS strategy_name,
                        d.mode,
                        d.status AS deployment_status,
                        d.proposed_at,
                        d.activated_at,
                        COALESCE((
                            SELECT walk_forward_score
                            FROM walk_forward_analysis
                            WHERE strategy_id = d.strategy_id::text
                            ORDER BY analyzed_at DESC LIMIT 1
                        ), 0) AS wf_score,
                        COALESCE((
                            SELECT overfit_probability
                            FROM overfitting_analysis
                            WHERE strategy_id = d.strategy_id::text
                            ORDER BY analyzed_at DESC LIMIT 1
                        ), 1.0) AS overfit_prob,
                        COALESCE((
                            SELECT regime_survival_score
                            FROM regime_validation
                            WHERE strategy_id = d.strategy_id::text
                            ORDER BY validated_at DESC LIMIT 1
                        ), 0.0) AS regime_survival,
                        COALESCE((
                            SELECT monte_carlo_survival_score
                            FROM monte_carlo_analysis
                            WHERE strategy_id = d.strategy_id::text
                            ORDER BY simulated_at DESC LIMIT 1
                        ), 0.0) AS mc_survival
                    FROM deployment_governance d
                    LEFT JOIN strategies s ON s.id::text = d.strategy_id::text
                    ORDER BY d.proposed_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            deployments = []
            active_regressed = 0
            total_active = 0
            for row in r.fetchall():
                wf = float(row[7] or 0)
                of = float(row[8] or 1.0)
                rs = float(row[9] or 0.0)
                mc = float(row[10] or 0.0)

                # Compute regression signals (same logic as deployment_governor._detect_regression)
                regression_signals = 0
                if wf < 20.0:
                    regression_signals += 1
                if of > 0.6:
                    regression_signals += 1
                if rs < 0.2:
                    regression_signals += 1
                if mc < 0.3:
                    regression_signals += 1

                is_regressed = regression_signals >= 2

                dep_status = str(row[4]) if row[4] else ""
                if dep_status in ("paper", "shadow", "partial_live", "live"):
                    total_active += 1
                    if is_regressed:
                        active_regressed += 1

                deployments.append({
                    "deployment_id": str(row[0]),
                    "strategy_id": str(row[1]),
                    "strategy_name": str(row[2]) if row[2] else "unknown",
                    "mode": str(row[3]) if row[3] else "",
                    "status": dep_status,
                    "proposed_at": str(row[5]) if row[5] else "",
                    "activated_at": str(row[6]) if row[6] else None,
                    "regression": {
                        "walk_forward_score": round(wf, 2),
                        "overfit_probability": round(of, 2),
                        "regime_survival": round(rs, 2),
                        "monte_carlo_survival": round(mc, 2),
                        "signals_fired": regression_signals,
                        "is_regressed": is_regressed,
                    },
                })

            # 2. Rollback history summary
            r = await conn.execute(
                text("""
                    SELECT
                        d.id, d.strategy_id, s.name AS strategy_name,
                        d.mode, d.approved_by, d.proposed_at, d.activated_at,
                        d.updated_at
                    FROM deployment_governance d
                    LEFT JOIN strategies s ON s.id::text = d.strategy_id::text
                    WHERE d.status = 'rolled_back'
                    ORDER BY d.updated_at DESC
                    LIMIT 20
                """)
            )
            rollbacks = []
            for row in r.fetchall():
                rollbacks.append({
                    "deployment_id": str(row[0]),
                    "strategy_id": str(row[1]),
                    "strategy_name": str(row[2]) if row[2] else "unknown",
                    "mode": str(row[3]) if row[3] else "",
                    "approved_by": str(row[4]) if row[4] else "",
                    "proposed_at": str(row[5]) if row[5] else "",
                    "activated_at": str(row[6]) if row[6] else None,
                    "rolled_back_at": str(row[7]) if row[7] else "",
                })

            # 3. Summary stats
            r = await conn.execute(text("SELECT COUNT(*) FROM deployment_governance"))
            total_deployments = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'rolled_back'")
            )
            total_rollbacks = r.scalar() or 0

            r = await conn.execute(
                text("SELECT COUNT(*) FROM deployment_governance WHERE status = 'rejected'")
            )
            total_rejected = r.scalar() or 0

        return {
            "summary": {
                "total_deployments": total_deployments,
                "active_deployments": total_active,
                "active_regressed": active_regressed,
                "total_rollbacks": total_rollbacks,
                "total_rejected": total_rejected,
                "regression_rate_pct": round((active_regressed / total_active * 100), 1) if total_active > 0 else 0.0,
            },
            "deployments": deployments,
            "rollbacks": rollbacks,
        }
    except Exception as exc:
        logger.error(f"Dashboard regression error: {exc}")
        return {"error": str(exc)}

