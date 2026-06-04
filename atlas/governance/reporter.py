from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
from .persistence import GovernancePersistenceLayer


@dataclass
class GovernanceMetricsReporter:
    persistence: GovernancePersistenceLayer

    def operation_distribution(self, session_id: str) -> Dict[str, int]:
        # naive: count operations by scanning operation log
        from sqlalchemy import select, func

        op_table = self.persistence.operation_log
        s = select(op_table.c.operation, func.count(op_table.c.operation).label("cnt")).where(op_table.c.session_id == session_id).group_by(op_table.c.operation)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return {r[0]: int(r[1]) for r in rows}

    def top_violation_signatures(self, session_id: str, limit: int = 10) -> List[Dict[str, int]]:
        from sqlalchemy import select, func

        dl = self.persistence.decision_log
        s = select(dl.c.violation, func.count(dl.c.violation).label("cnt")).where(dl.c.session_id == session_id).group_by(dl.c.violation).order_by(func.count(dl.c.violation).desc()).limit(limit)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return [{"violation": r[0], "count": int(r[1])} for r in rows]

    def repair_hotspots(self, session_id: str, limit: int = 10):
        from sqlalchemy import select, func
        t = self.persistence.repair_events
        s = select(t.c.operation, func.count(t.c.operation).label("cnt")).where(t.c.session_id == session_id).group_by(t.c.operation).order_by(func.count(t.c.operation).desc()).limit(limit)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return [{"operation": r[0], "count": int(r[1])} for r in rows]

    def bypass_hotspots(self, session_id: str, limit: int = 10):
        from sqlalchemy import select, func
        t = self.persistence.bypass_events
        s = select(t.c.operation, func.count(t.c.operation).label("cnt")).where(t.c.session_id == session_id).group_by(t.c.operation).order_by(func.count(t.c.operation).desc()).limit(limit)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return [{"operation": r[0], "count": int(r[1])} for r in rows]

    def lineage_fracture_sources(self, session_id: str, limit: int = 10):
        from sqlalchemy import select, func
        t = self.persistence.lineage_failures
        s = select(t.c.context, func.count(t.c.context).label("cnt")).where(t.c.session_id == session_id).group_by(t.c.context).order_by(func.count(t.c.context).desc()).limit(limit)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return [{"context": r[0], "count": int(r[1])} for r in rows]

    def trace_discontinuity_sources(self, session_id: str, limit: int = 10):
        from sqlalchemy import select, func
        t = self.persistence.trace_failures
        s = select(t.c.context, func.count(t.c.context).label("cnt")).where(t.c.session_id == session_id).group_by(t.c.context).order_by(func.count(t.c.context).desc()).limit(limit)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return [{"context": r[0], "count": int(r[1])} for r in rows]

    def governance_summary(self, session_id: str) -> Dict[str, any]:
        # produce computed metrics and top lists
        ops = self.operation_distribution(session_id)
        violations = self.top_violation_signatures(session_id)
        repairs = self.repair_hotspots(session_id)
        bypasses = self.bypass_hotspots(session_id)
        lineage = self.lineage_fracture_sources(session_id)
        traces = self.trace_discontinuity_sources(session_id)

        return {
            "operations": ops,
            "top_violations": violations,
            "repair_hotspots": repairs,
            "bypass_hotspots": bypasses,
            "lineage_fractures": lineage,
            "trace_discontinuities": traces,
        }
