from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path

from .persistence import GovernancePersistenceLayer


@dataclass
class GovernanceAnalyticsEngine:
    persistence: GovernancePersistenceLayer
    journal_path: Path = Path(__file__).resolve().parent / "identity_violation_journal.log"

    def load_journal(self) -> List[Dict[str, Any]]:
        entries = []
        if not self.journal_path.exists():
            return entries
        with open(self.journal_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    # legacy: try eval fallback
                    try:
                        entries.append(eval(line))
                    except Exception:
                        continue
        return entries

    def governance_coverage_percent(self, session_id: str) -> float:
        # Normalize by distinct event_id across all governance sources (operation_log, decision_log, bypass, repair, failures, quarantine, journal)
        all_event_ids = set()
        from sqlalchemy import text
        with self.persistence.engine.begin() as conn:
            tables = (
                "governance_operation_log",
                "governance_decision_log",
                "governance_bypass_events",
                "governance_repair_events",
                "lineage_integrity_failures",
                "trace_continuity_failures",
                "quarantine_registry",
            )
            for tbl in tables:
                try:
                    rows = conn.execute(text(f"SELECT DISTINCT event_id FROM {tbl} WHERE session_id=:s"), {"s": session_id}).fetchall()
                    for r in rows:
                        if r and r[0]:
                            all_event_ids.add(r[0])
                except Exception:
                    continue

        # include journaled event_ids
        for entry in self.load_journal():
            rec = entry.get("record") if isinstance(entry, dict) else None
            if not rec:
                continue
            payload = rec.get("payload") if isinstance(rec, dict) else None
            if isinstance(payload, dict):
                em = payload.get("event_meta")
                if isinstance(em, dict) and em.get("event_id"):
                    all_event_ids.add(em.get("event_id"))

        total = len(all_event_ids)

        # governed events: those with decisions/bypasses/repairs/journal entries
        governed_ids = set()
        with self.persistence.engine.begin() as conn:
            for tbl in ("governance_decision_log", "governance_bypass_events", "governance_repair_events"):
                try:
                    rows = conn.execute(text(f"SELECT DISTINCT event_id FROM {tbl} WHERE session_id=:s"), {"s": session_id}).fetchall()
                    for r in rows:
                        if r and r[0]:
                            governed_ids.add(r[0])
                except Exception:
                    continue
        for entry in self.load_journal():
            rec = entry.get("record") if isinstance(entry, dict) else None
            if not rec:
                continue
            payload = rec.get("payload") if isinstance(rec, dict) else None
            if isinstance(payload, dict):
                em = payload.get("event_meta")
                if isinstance(em, dict) and em.get("event_id"):
                    governed_ids.add(em.get("event_id"))

        governed = len(governed_ids)
        if total == 0:
            return 0.0
        return 100.0 * (governed / total)

    def bypass_rate_percent(self, session_id: str) -> float:
        # compute based on distinct events
        from sqlalchemy import text
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT event_id FROM governance_operation_log WHERE session_id=:s"), {"s": session_id}).fetchall()
        evs = {r[0] for r in rows if r and r[0]}
        total = len(evs)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT event_id FROM governance_bypass_events WHERE session_id=:s"), {"s": session_id}).fetchall()
        bypasses = len({r[0] for r in rows if r and r[0]})
        if total == 0:
            return 0.0
        return 100.0 * (bypasses / total)

    def repair_dependency_percent(self, session_id: str) -> float:
        # compute based on distinct events
        from sqlalchemy import text
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT event_id FROM governance_operation_log WHERE session_id=:s"), {"s": session_id}).fetchall()
        evs = {r[0] for r in rows if r and r[0]}
        total = len(evs)
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT event_id FROM governance_repair_events WHERE session_id=:s"), {"s": session_id}).fetchall()
        repairs = len({r[0] for r in rows if r and r[0]})
        if total == 0:
            return 0.0
        return 100.0 * (repairs / total)

    def extract_violation_signatures(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        # signatures from journal: group by tuple (violation_type, operation, component, table, field)
        entries = self.load_journal()
        sig_counter = Counter()
        for e in entries:
            v = e.get("violation") if isinstance(e, dict) else None
            if isinstance(v, dict):
                key = (
                    v.get("violation_type") or v.get("type") or "unknown",
                    v.get("operation") or v.get("op") or "unknown",
                    v.get("component") or "unknown",
                    v.get("table") or "unknown",
                    v.get("field") or "unknown",
                )
            else:
                # try parse string
                key = (str(v)[:80], "", "", "", "")
            sig_counter[key] += 1
        results = []
        for k, cnt in sig_counter.most_common(limit):
            results.append({
                "violation_type": k[0],
                "operation_type": k[1],
                "component": k[2],
                "table": k[3],
                "field": k[4],
                "count": cnt,
            })
        return results

    def repair_hotspots(self, session_id: str, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        # most repaired fields/components/tables/ops
        from sqlalchemy import select, func

        t = self.persistence.repair_events
        with self.persistence.engine.begin() as conn:
            rows = conn.execute(select(t.c.original, t.c.repaired)).fetchall()
        field_counter = Counter()
        comp_counter = Counter()
        table_counter = Counter()
        op_counter = Counter()
        for orig, rep in rows:
            # best-effort: parse JSON-like original/repaired strings
            try:
                o = json.loads(orig)
            except Exception:
                o = {}
            try:
                r = json.loads(rep)
            except Exception:
                r = {}
            # heuristics
            if isinstance(o, dict):
                for f in o.keys():
                    field_counter[f] += 1
            comp = o.get("component") if isinstance(o, dict) else None
            tbl = o.get("table") if isinstance(o, dict) else None
            op = o.get("operation") if isinstance(o, dict) else None
            if comp:
                comp_counter[comp] += 1
            if tbl:
                table_counter[tbl] += 1
            if op:
                op_counter[op] += 1

        return {
            "fields": [{"field": k, "count": v} for k, v in field_counter.most_common(limit)],
            "components": [{"component": k, "count": v} for k, v in comp_counter.most_common(limit)],
            "tables": [{"table": k, "count": v} for k, v in table_counter.most_common(limit)],
            "operations": [{"operation": k, "count": v} for k, v in op_counter.most_common(limit)],
        }

    def lineage_integrity_metrics(self, session_id: str) -> Dict[str, Any]:
        total_lineage_failures = self.persistence.query_counts(self.persistence.lineage_failures, session_id)
        orphan_lineage_count = total_lineage_failures  # heuristic
        lineage_repair_freq = self.persistence.query_counts(self.persistence.repair_events, session_id)
        # compute a simple score: 100 - normalized failures
        total_ops = max(1, self.persistence.query_counts(self.persistence.operation_log, session_id))
        score = max(0.0, 100.0 - (100.0 * (total_lineage_failures / total_ops)))
        return {
            "lineage_integrity_score": score,
            "orphan_lineage_count": orphan_lineage_count,
            "lineage_repair_frequency": lineage_repair_freq,
            "lineage_continuity_failures": total_lineage_failures,
        }

    def trace_continuity_metrics(self, session_id: str) -> Dict[str, Any]:
        total_trace_failures = self.persistence.query_counts(self.persistence.trace_failures, session_id)
        total_ops = max(1, self.persistence.query_counts(self.persistence.operation_log, session_id))
        score = max(0.0, 100.0 - (100.0 * (total_trace_failures / total_ops)))
        trace_repair_dep = self.persistence.query_counts(self.persistence.repair_events, session_id)
        return {
            "trace_continuity_score": score,
            "trace_break_count": total_trace_failures,
            "invalid_trace_frequency": total_trace_failures / total_ops,
            "trace_repair_dependency": trace_repair_dep,
        }

    def compute_all(self, session_id: str) -> Dict[str, Any]:
        out = {}
        out["governance_coverage_percent"] = self.governance_coverage_percent(session_id)
        out["bypass_rate_percent"] = self.bypass_rate_percent(session_id)
        out["repair_dependency_percent"] = self.repair_dependency_percent(session_id)
        out["violation_signatures"] = self.extract_violation_signatures(session_id)
        out["repair_hotspots"] = self.repair_hotspots(session_id)
        out["lineage_metrics"] = self.lineage_integrity_metrics(session_id)
        out["trace_metrics"] = self.trace_continuity_metrics(session_id)
        # persist snapshot
        try:
            self.persistence.persist_snapshot(session_id, out)
        except Exception:
            pass
        return out
