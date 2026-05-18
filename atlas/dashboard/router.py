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
            active_keys = r.scalar() or 0

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
                "active": False,
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
