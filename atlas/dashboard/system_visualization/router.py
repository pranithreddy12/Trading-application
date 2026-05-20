"""System Visualization — Trace graphs, mutation lineage, scout influence, portfolio exposure, systemic risk, replay timelines."""

from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

from atlas.config.settings import settings

system_viz_router = APIRouter(prefix="/system-viz", tags=["System Visualization"])


async def _get_db():
    from atlas.data.storage.timescale_client import TimescaleClient
    db = TimescaleClient(settings.database_url)
    await db.connect()
    return db


@system_viz_router.get("/trace-graph")
async def trace_graph(limit: int = 50):
    """Reconstruct causal chains from lifecycle events."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT trace_id, stage, status, actor, strategy_id, parent_event_id, created_at
                    FROM lifecycle_events
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            events = [dict(row._mapping) for row in r.fetchall()]
            for e in events:
                for k in ("created_at",):
                    if hasattr(e.get(k), "isoformat"):
                        e[k] = e[k].isoformat()
        return {"events": events, "n_events": len(events)}
    except Exception as exc:
        return {"error": str(exc)}


@system_viz_router.get("/mutation-lineage")
async def mutation_lineage(limit: int = 50):
    """Visualize mutation parent-child relationships."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT parent_strategy_id, child_strategy_id, mutation_type,
                           sharpe_delta, score_delta, improved, created_at
                    FROM mutation_memory
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            mutations = [dict(row._mapping) for row in r.fetchall()]
            for m in mutations:
                for k in ("created_at",):
                    if hasattr(m.get(k), "isoformat"):
                        m[k] = m[k].isoformat()
        return {"mutations": mutations}
    except Exception as exc:
        return {"error": str(exc)}


@system_viz_router.get("/portfolio-exposure")
async def portfolio_exposure():
    """Latest portfolio exposure map."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT computed_at, method, final_allocations, total_exposure
                    FROM capital_allocation
                    ORDER BY computed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                return {
                    "computed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "method": row[1],
                    "allocations": row[2],
                    "total_exposure": float(row[3]) if row[3] else 0,
                }
            return {"message": "No allocation data"}
    except Exception as exc:
        return {"error": str(exc)}


@system_viz_router.get("/systemic-risk")
async def systemic_risk_view():
    """Latest systemic risk assessment."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT assessed_at, systemic_risk_score, contagion_probability,
                           portfolio_fragility, correlation_regime
                    FROM systemic_risk
                    ORDER BY assessed_at DESC LIMIT 1
                """)
            )
            row = r.fetchone()
            if row:
                return {
                    "assessed_at": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "systemic_risk_score": float(row[1]) if row[1] else 0,
                    "contagion_probability": float(row[2]) if row[2] else 0,
                    "portfolio_fragility": float(row[3]) if row[3] else 0,
                    "correlation_regime": float(row[4]) if row[4] else 0,
                }
            return {"message": "No systemic risk data"}
    except Exception as exc:
        return {"error": str(exc)}


@system_viz_router.get("/scout-influence")
async def scout_influence(limit: int = 50):
    """Visualize scout signal influence on strategies."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT source, timestamp, sentiment, hypothesis_score,
                           signal_direction, mentioned_tickers
                    FROM external_scout_memory
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            signals = [dict(row._mapping) for row in r.fetchall()]
            for s in signals:
                for k in ("timestamp",):
                    if hasattr(s.get(k), "isoformat"):
                        s[k] = s[k].isoformat()
        return {"signals": signals}
    except Exception as exc:
        return {"error": str(exc)}


@system_viz_router.get("/replay-timeline")
async def replay_timeline(limit: int = 100):
    """Event store replay timeline."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT id, aggregate_id, aggregate_type, event_type,
                           trace_id, parent_event_id, created_at
                    FROM event_store
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            events = [dict(row._mapping) for row in r.fetchall()]
            for e in events:
                for k in ("created_at",):
                    if hasattr(e.get(k), "isoformat"):
                        e[k] = e[k].isoformat()
        return {"events": events}
    except Exception as exc:
        return {"error": str(exc)}
