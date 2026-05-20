"""
EventLineageClient — Cross-system trace_id tracking for full lifecycle audit.

Tracks every strategy through: Ideator → Coder → Backtest → Pattern → Brief → CopyTrader
Enables query: "What happened to this strategy, when, and by which agent?"
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from atlas.core.serialization import normalize_db_params, safe_json_dumps


@dataclass
class LifecycleEvent:
    id: str
    trace_id: str
    strategy_id: Optional[str]
    stage: str
    status: str
    actor: str
    parent_event_id: Optional[str]
    metadata: dict
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class EventLineageClient:
    """
    Event lineage and trace_id management.

    Usage:
        lineage = EventLineageClient(db)
        trace_id = await lineage.create_trace(strategy_id, "ideator", "my_agent")
        await lineage.create_event(trace_id, "coder", "completed", "coder_agent",
                                   strategy_id=strategy_id, metadata={"code_len": 512})
        events = await lineage.get_lineage(trace_id)
    """

    def __init__(self, db):
        self.db = db

    async def create_trace(
        self,
        strategy_id: str,
        stage: str = "ideator",
        actor: str = "",
        metadata: Optional[dict] = None,
    ) -> str:
        """Generate a new trace_id and create the first lifecycle event. Returns trace_id."""
        trace_id = uuid.uuid4().hex[:16]
        await self.create_event(
            trace_id=trace_id,
            stage=stage,
            status="completed",
            actor=actor or "system",
            strategy_id=strategy_id,
            metadata=metadata or {},
        )
        return trace_id

    async def create_event(
        self,
        trace_id: str,
        stage: str,
        status: str,
        actor: str,
        strategy_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Create a lifecycle event and return its ID."""
        event_id = uuid.uuid4().hex[:16]
        from sqlalchemy.sql import text

        async with self.db.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO lifecycle_events
                        (id, trace_id, strategy_id, stage, status, actor,
                         parent_event_id, metadata, created_at)
                    VALUES
                        (:id, :trace_id, :strategy_id, :stage, :status, :actor,
                         :parent_event_id, :metadata, NOW())
                """),
                normalize_db_params({
                    "id": event_id,
                    "trace_id": trace_id,
                    "strategy_id": str(strategy_id) if strategy_id is not None else None,
                    "stage": stage,
                    "status": status,
                    "actor": actor,
                    "parent_event_id": str(parent_event_id) if parent_event_id is not None else None,
                    "metadata": safe_json_dumps(metadata or {}),
                }),
            )
        return event_id

    async def get_lineage(self, trace_id: str) -> list[LifecycleEvent]:
        """Get all events for a trace_id, ordered by time."""
        from sqlalchemy.sql import text

        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, trace_id, strategy_id, stage, status, actor,
                           parent_event_id, metadata, created_at
                    FROM lifecycle_events
                    WHERE trace_id = :trace_id
                    ORDER BY created_at ASC
                """),
                {"trace_id": trace_id},
            )
            rows = result.fetchall()
            cols = [
                "id",
                "trace_id",
                "strategy_id",
                "stage",
                "status",
                "actor",
                "parent_event_id",
                "metadata",
                "created_at",
            ]
            return [
                LifecycleEvent(
                    id=str(row[0]),
                    trace_id=str(row[1]),
                    strategy_id=str(row[2]) if row[2] else None,
                    stage=str(row[3]),
                    status=str(row[4]),
                    actor=str(row[5]),
                    parent_event_id=str(row[6]) if row[6] else None,
                    metadata=json.loads(row[7])
                    if isinstance(row[7], str)
                    else (row[7] or {}),
                    created_at=row[8].isoformat()
                    if hasattr(row[8], "isoformat")
                    else str(row[8]),
                )
                for row in rows
            ]

    async def get_trace_by_strategy(self, strategy_id: str) -> Optional[str]:
        """Get the trace_id for a strategy (first matching event)."""
        from sqlalchemy.sql import text

        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT trace_id FROM lifecycle_events
                    WHERE strategy_id = :strategy_id
                    ORDER BY created_at ASC
                    LIMIT 1
                """),
                {"strategy_id": strategy_id},
            )
            row = result.fetchone()
            return str(row[0]) if row else None

    async def get_lineage_summary(self, trace_id: str) -> dict:
        """
        Get a structured summary of the full lineage chain.
        Returns list of stages completed, timing, and status.
        """
        events = await self.get_lineage(trace_id)
        if not events:
            return {
                "trace_id": trace_id,
                "events": [],
                "stages_completed": 0,
                "status": "unknown",
            }

        stages = []
        for e in events:
            stages.append(
                {
                    "stage": e.stage,
                    "status": e.status,
                    "actor": e.actor,
                    "time": e.created_at,
                    "metadata": e.metadata,
                }
            )

        return {
            "trace_id": trace_id,
            "strategy_id": events[0].strategy_id,
            "stages_completed": len(events),
            "stages": stages,
            "first_event": events[0].created_at,
            "last_event": events[-1].created_at,
            "status": "complete"
            if all(e.status == "completed" for e in events)
            else "incomplete",
        }

    async def get_all_traces(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get all distinct trace_ids with basic summary info."""
        from sqlalchemy.sql import text

        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        trace_id,
                        COUNT(*) as event_count,
                        MIN(created_at) as first_event,
                        MAX(created_at) as last_event,
                        COUNT(DISTINCT strategy_id) as strategy_count
                    FROM lifecycle_events
                    GROUP BY trace_id
                    ORDER BY last_event DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset},
            )
            rows = result.fetchall()
            return [
                {
                    "trace_id": str(row[0]),
                    "event_count": row[1],
                    "first_event": row[2].isoformat()
                    if hasattr(row[2], "isoformat")
                    else str(row[2]),
                    "last_event": row[3].isoformat()
                    if hasattr(row[3], "isoformat")
                    else str(row[3]),
                    "strategy_count": row[4],
                }
                for row in rows
            ]
