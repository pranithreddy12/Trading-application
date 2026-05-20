"""
trace_graph_engine.py — Full-system trace propagation and causal chain reconstruction.

Builds directed acyclic graphs from event_store and lifecycle_events.
Enables:
- Causal chain reconstruction
- Orphaned flow detection
- Delayed flow identification
- System execution path visualization
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy.sql import text


class TraceGraphEngine:
    """
    Reconstructs and analyzes causal chains across the entire ATLAS system.

    Uses event_store for fine-grained events and lifecycle_events for high-level stages.
    """

    def __init__(self, db):
        self.db = db

    async def get_full_lineage(
        self,
        trace_id: str,
    ) -> list[dict]:
        """Get all events and lifecycle entries for a trace in causal order."""
        async with self.db.engine.connect() as conn:
            # Get lifecycle events
            r = await conn.execute(
                text("""
                    SELECT id, trace_id, strategy_id, stage, status, actor,
                           parent_event_id, metadata, created_at
                    FROM lifecycle_events
                    WHERE trace_id = :trace_id
                    ORDER BY created_at ASC
                """),
                {"trace_id": trace_id},
            )
            lifecycle = []
            for row in r.fetchall():
                meta = row[7]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                lifecycle.append({
                    "id": str(row[0]),
                    "type": "lifecycle",
                    "stage": str(row[3]),
                    "status": str(row[4]),
                    "actor": str(row[5]),
                    "parent_event_id": str(row[6]) if row[6] else None,
                    "metadata": meta,
                    "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
                })

            # Get event store entries
            r = await conn.execute(
                text("""
                    SELECT id, event_type, version, parent_event_id,
                           aggregate_type, data, metadata, created_at
                    FROM event_store
                    WHERE trace_id = :trace_id
                    ORDER BY created_at ASC
                """),
                {"trace_id": trace_id},
            )
            events = []
            for row in r.fetchall():
                data_raw = row[5]
                if isinstance(data_raw, str):
                    try:
                        data_raw = json.loads(data_raw)
                    except Exception:
                        data_raw = {}
                meta_raw = row[6]
                if isinstance(meta_raw, str):
                    try:
                        meta_raw = json.loads(meta_raw)
                    except Exception:
                        meta_raw = {}
                events.append({
                    "id": str(row[0]),
                    "type": "event",
                    "event_type": str(row[1]),
                    "aggregate_type": str(row[4]) if row[4] else "",
                    "data": data_raw,
                    "metadata": meta_raw,
                    "parent_event_id": str(row[3]) if row[3] else None,
                    "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                })

        # Merge and sort by time
        combined = sorted(
            lifecycle + events,
            key=lambda x: x["created_at"],
        )

        return combined

    async def detect_orphaned_flows(self, hours: int = 24) -> list[dict]:
        """
        Detect traces with no terminal event (completed/failed) in the window.
        """
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT l1.trace_id,
                           COUNT(*) as event_count,
                           MIN(l1.created_at) as first_event,
                           MAX(l1.created_at) as last_event
                    FROM lifecycle_events l1
                    WHERE NOT EXISTS (
                        SELECT 1 FROM lifecycle_events l2
                        WHERE l2.trace_id = l1.trace_id
                          AND l2.status IN ('completed', 'failed', 'cancelled')
                    )
                    AND l1.created_at > NOW() - INTERVAL ':hours hours'
                    GROUP BY l1.trace_id
                    ORDER BY last_event DESC
                """),
                {"hours": hours},
            )
            return [
                {
                    "trace_id": str(row[0]),
                    "event_count": row[1],
                    "first_event": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                    "last_event": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                }
                for row in r.fetchall()
            ]

    async def detect_delayed_flows(self, threshold_minutes: int = 30) -> list[dict]:
        """
        Detect traces where events have stalled between stages.
        """
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    WITH trace_timing AS (
                        SELECT trace_id,
                               MIN(created_at) as first_event,
                               MAX(created_at) as last_event,
                               COUNT(*) as event_count,
                               COUNT(DISTINCT stage) as stages_completed
                        FROM lifecycle_events
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        GROUP BY trace_id
                    )
                    SELECT trace_id, event_count, stages_completed,
                           first_event, last_event,
                           EXTRACT(EPOCH FROM (last_event - first_event)) / 60 as duration_minutes
                    FROM trace_timing
                    WHERE EXTRACT(EPOCH FROM (NOW() - last_event)) / 60 > :threshold
                      AND NOT EXISTS (
                          SELECT 1 FROM lifecycle_events l2
                          WHERE l2.trace_id = trace_timing.trace_id
                            AND l2.status IN ('completed', 'failed')
                      )
                    ORDER BY duration_minutes DESC
                """),
                {"threshold": threshold_minutes},
            )
            return [
                {
                    "trace_id": str(row[0]),
                    "event_count": row[1],
                    "stages_completed": row[2],
                    "first_event": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                    "last_event": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                    "duration_minutes": float(row[5]) if row[5] else 0,
                }
                for row in r.fetchall()
            ]

    async def get_causal_chain(
        self,
        start_event_id: str,
        direction: str = "forward",
        max_depth: int = 10,
    ) -> list[dict]:
        """
        Walk the parent-child event graph to build a causal chain.
        direction='forward' follows children, 'backward' follows parents.
        """
        chain = []
        visited = set()
        current_id = start_event_id

        for _ in range(max_depth):
            if not current_id or current_id in visited:
                break
            visited.add(current_id)

            if direction == "forward":
                async with self.db.engine.connect() as conn:
                    r = await conn.execute(
                        text("""
                            SELECT e1.id, e1.event_type, e1.trace_id,
                                   e1.aggregate_type, e1.data, e1.parent_event_id,
                                   e1.created_at
                            FROM event_store e1
                            WHERE e1.parent_event_id = :current_id
                            ORDER BY e1.created_at ASC
                            LIMIT 1
                        """),
                        {"current_id": current_id},
                    )
                    row = r.fetchone()
                    if not row:
                        break
                    current_id = str(row[0])
                    data_raw = row[4]
                    if isinstance(data_raw, str):
                        try:
                            data_raw = json.loads(data_raw)
                        except Exception:
                            data_raw = {}
                    chain.append({
                        "id": current_id,
                        "event_type": str(row[1]),
                        "trace_id": str(row[2]),
                        "aggregate_type": str(row[3]) if row[3] else "",
                        "data": data_raw,
                        "parent_event_id": str(row[5]) if row[5] else None,
                        "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                    })
            else:
                async with self.db.engine.connect() as conn:
                    r = await conn.execute(
                        text("""
                            SELECT id, event_type, trace_id,
                                   aggregate_type, data, parent_event_id,
                                   created_at
                            FROM event_store
                            WHERE id = :current_id
                            LIMIT 1
                        """),
                        {"current_id": current_id},
                    )
                    row = r.fetchone()
                    if not row:
                        break
                    data_raw = row[4]
                    if isinstance(data_raw, str):
                        try:
                            data_raw = json.loads(data_raw)
                        except Exception:
                            data_raw = {}
                    chain.append({
                        "id": str(row[0]),
                        "event_type": str(row[1]),
                        "trace_id": str(row[2]),
                        "aggregate_type": str(row[3]) if row[3] else "",
                        "data": data_raw,
                        "parent_event_id": str(row[5]) if row[5] else None,
                        "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                    })
                    current_id = str(row[5]) if row[5] else None

        return chain

    async def get_flow_statistics(
        self,
        hours: int = 24,
    ) -> dict:
        """Get flow statistics for the system."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT
                        COUNT(DISTINCT trace_id) as total_traces,
                        COUNT(*) as total_events,
                        COUNT(DISTINCT stage) as unique_stages,
                        COUNT(DISTINCT actor) as unique_actors,
                        AVG(
                            CASE WHEN status = 'completed' THEN 1 ELSE 0 END
                        ) as completion_rate
                    FROM lifecycle_events
                    WHERE created_at > NOW() - INTERVAL ':hours hours'
                """),
                {"hours": hours},
            )
            row = r.fetchone()
            if not row:
                return {}

            r2 = await conn.execute(
                text("""
                    SELECT stage, COUNT(*) as cnt
                    FROM lifecycle_events
                    WHERE created_at > NOW() - INTERVAL ':hours hours'
                    GROUP BY stage
                    ORDER BY cnt DESC
                """),
                {"hours": hours},
            )
            stages = {str(r[0]): r[1] for r in r2.fetchall()}

            return {
                "total_traces": row[0],
                "total_events": row[1],
                "unique_stages": row[2],
                "unique_actors": row[3],
                "completion_rate": float(row[4]) if row[4] else 0.0,
                "stages": stages,
            }
