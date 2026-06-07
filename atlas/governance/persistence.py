from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    create_engine,
    event,
    select,
)
from sqlalchemy import text
from atlas.governance import state as governance_state
from atlas.governance import identity_authority
from atlas.governance import hashing as _hashing
try:
    from atlas.core.persistence_integrity import IdentityContractViolation
except Exception:
    class IdentityContractViolation(Exception):
        pass

DB_PATH = Path(__file__).resolve().parent / "governance.db"


class GovernancePersistenceLayer:
    """Simple SQLite-backed persistence for Phase 38 governance.

    Tables are append-only and include a `session_id` to group runs.
    """

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or f"sqlite:///{DB_PATH}"
        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        # Sprint 1E — governance.db is a single-writer SQLite sitting in the backtest
        # hot path. Tune connection-level pragmas for throughput + concurrency WITHOUT
        # changing any governance logic or what gets recorded:
        #   WAL                -> writers don't block readers; no whole-file lock
        #                         (lets multiple BacktestRunners coexist safely)
        #   synchronous=NORMAL -> fsync at checkpoint, not every commit (safe under WAL)
        #   busy_timeout       -> wait for the lock instead of erroring "database is locked"
        if str(self.db_url).startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragmas(dbapi_conn, _rec):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=30000")
                cur.close()
        self.metadata = MetaData()
        # Core tables
        self.operation_log = Table(
            "governance_operation_log",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("canonical_event_hash", String(128)),
            Column("parent_event_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("operation", String(64)),
            Column("identity_type", String(64)),
            Column("context", String(255)),
            Column("payload", Text),
            Column("event_state", String(32)),
        )

        self.decision_log = Table(
            "governance_decision_log",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("decision", String(32)),
            Column("severity", String(32)),
            Column("violation", Text),
            Column("event_state", String(32)),
        )

        self.bypass_events = Table(
            "governance_bypass_events",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("operation", String(64)),
            Column("reason", Text),
            Column("shadow_tag", String(32)),
            Column("event_state", String(32)),
        )

        self.repair_events = Table(
            "governance_repair_events",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("operation", String(64)),
            Column("original", Text),
            Column("repaired", Text),
            Column("shadow_tag", String(32)),
            Column("event_state", String(32)),
        )

        self.lineage_failures = Table(
            "lineage_integrity_failures",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("context", String(255)),
            Column("details", Text),
            Column("event_state", String(32)),
        )

        self.trace_failures = Table(
            "trace_continuity_failures",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("root_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("causal_depth", Integer),
            Column("operation_hash", String(128)),
            Column("replay_epoch", Integer),
            Column("timestamp_ns", Integer),
            Column("context", String(255)),
            Column("details", Text),
            Column("event_state", String(32)),
        )

        self.quarantine = Table(
            "quarantine_registry",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("event_id", String(64), index=True),
            Column("parent_event_id", String(64)),
            Column("operation_sequence", Integer),
            Column("interception_stage", String(64)),
            Column("operation_hash", String(128)),
            Column("resource_id", String(128)),
            Column("reason", Text),
            Column("shadow_tag", String(32)),
            Column("event_state", String(32)),
        )

        self.metadata.create_all(self.engine)
        # Best-effort migration: use sqlite3 directly to add missing columns if DB already exists
        try:
            import sqlite3, os

            db_file = None
            if self.db_url and self.db_url.startswith("sqlite:///"):
                db_file = self.db_url.replace("sqlite:///", "")
            elif DB_PATH:
                db_file = str(DB_PATH)
            if db_file and os.path.exists(db_file):
                conn = sqlite3.connect(db_file)
                cur = conn.cursor()
                tables = [
                    "governance_operation_log",
                    "governance_decision_log",
                    "governance_bypass_events",
                    "governance_repair_events",
                    "lineage_integrity_failures",
                    "trace_continuity_failures",
                    "quarantine_registry",
                ]
                extras = [
                    ("event_id", "VARCHAR(64)"),
                    ("parent_event_id", "VARCHAR(64)"),
                    ("operation_sequence", "INTEGER"),
                    ("interception_stage", "VARCHAR(64)"),
                    ("operation_hash", "VARCHAR(128)"),
                    ("canonical_event_hash", "VARCHAR(128)"),
                    ("parent_event_hash", "VARCHAR(128)"),
                    ("root_event_id", "VARCHAR(64)"),
                    ("causal_depth", "INTEGER"),
                    ("replay_epoch", "INTEGER"),
                    ("timestamp_ns", "INTEGER"),
                    ("event_state", "VARCHAR(32)"),
                ]
                for tbl in tables:
                    try:
                        cur.execute(f"PRAGMA table_info({tbl})")
                        existing = [r[1] for r in cur.fetchall()]
                        for col, coltype in extras:
                            if col not in existing:
                                try:
                                    cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {coltype}")
                                except Exception:
                                    continue
                    except Exception:
                        continue
                conn.commit()
                conn.close()
        except Exception:
            pass

    def _now(self) -> datetime:
        return datetime.utcnow()

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def _state_from_str(self, s: Optional[str]):
        if not s:
            return None
        try:
            return governance_state.GovernanceEventState(s)
        except Exception:
            return None

    def _get_last_state(self, event_id: str):
        # Query latest event_state across core governance tables
        q = """
        SELECT event_state, timestamp FROM governance_operation_log WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM governance_decision_log WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM governance_bypass_events WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM governance_repair_events WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM lineage_integrity_failures WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM trace_continuity_failures WHERE event_id = :eid
        UNION ALL
        SELECT event_state, timestamp FROM quarantine_registry WHERE event_id = :eid
        ORDER BY timestamp DESC LIMIT 1
        """
        try:
            with self.engine.begin() as conn:
                r = conn.execute(text(q), {"eid": event_id}).fetchone()
            if not r:
                return None
            return self._state_from_str(r[0])
        except Exception:
            return None

    def _get_operation_canonical_event_hash(self, event_id: str) -> str | None:
        q = """
        SELECT canonical_event_hash
        FROM governance_operation_log
        WHERE event_id = :eid
        ORDER BY timestamp_ns DESC, id DESC
        LIMIT 1
        """
        try:
            with self.engine.begin() as conn:
                r = conn.execute(text(q), {"eid": event_id}).fetchone()
            if not r:
                return None
            return r[0]
        except Exception:
            return None

    def persist_operation(self, session_id: str, operation: str, identity_type: str, context: str, payload: str) -> None:
        # payload may include event identity fields as JSON string
        import json
        meta = {}
        try:
            j = json.loads(payload) if isinstance(payload, str) else payload
            meta = j.get("event_meta") if isinstance(j, dict) else {}
        except Exception:
            meta = {}
        # enforce canonical lifecycle: event_id must be present
        if not meta or not meta.get("event_id"):
            # record explicit contract violation and raise
            raise IdentityContractViolation(f"Missing event_id in persist_operation payload for session {session_id} operation {operation}")
        # Enforce causal identity authority if strict mode is enabled
        try:
            identity_authority.enforce_event_id_authority(meta)
        except Exception as e:
            # wrap into IdentityContractViolation for upstream handling
            raise IdentityContractViolation(str(e))
        # Compute canonical per-event hash BEFORE persistence using stable selection
        try:
            event_for_hash = {
                "event_id": meta.get("event_id"),
                "parent_event_id": meta.get("parent_event_id"),
                "root_event_id": meta.get("root_event_id"),
                "trace_id": meta.get("trace_id"),
                "strategy_id": meta.get("strategy_id"),
                "operation": operation,
                "event_state": meta.get("event_state"),
                "decision": meta.get("decision"),
                "replay_epoch": meta.get("replay_epoch"),
                "operation_sequence": meta.get("operation_sequence"),
            }
            canonical_event_hash = _hashing.event_hash(event_for_hash)
        except Exception:
            canonical_event_hash = None

        parent_event_hash = None
        parent_event_id = meta.get("parent_event_id")
        if parent_event_id:
            parent_event_hash = self._get_operation_canonical_event_hash(parent_event_id)
            if not parent_event_hash:
                raise IdentityContractViolation(
                    f"Missing parent_event_hash for parent_event_id {parent_event_id} in session {session_id} operation {operation}"
                )
        # validate transition if event_state provided
        new_state_str = meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.operation_log.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_state=meta.get("event_state"),
            event_id=meta.get("event_id"),
            parent_event_id=meta.get("parent_event_id"),
            root_event_id=meta.get("root_event_id"),
            operation_sequence=meta.get("operation_sequence"),
            interception_stage=meta.get("interception_stage"),
            causal_depth=meta.get("causal_depth"),
            operation_hash=meta.get("operation_hash"),
            canonical_event_hash=canonical_event_hash,
            parent_event_hash=parent_event_hash,
            replay_epoch=meta.get("replay_epoch"),
            timestamp_ns=meta.get("timestamp_ns"),
            operation=operation,
            identity_type=identity_type,
            context=context,
            payload=payload,
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_decision(self, session_id: str, decision: str, severity: str, violation: str, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_decision for session {session_id} decision {decision}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.decision_log.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            decision=decision,
            severity=severity,
            violation=violation,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_bypass(self, session_id: str, operation: str, reason: str, shadow_tag: Optional[str] = None, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_bypass for session {session_id} operation {operation}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.bypass_events.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            operation=operation,
            reason=reason,
            shadow_tag=shadow_tag,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_repair(self, session_id: str, operation: str, original: str, repaired: str, shadow_tag: Optional[str] = None, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_repair for session {session_id} operation {operation}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.repair_events.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            operation=operation,
            original=original,
            repaired=repaired,
            shadow_tag=shadow_tag,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_lineage_failure(self, session_id: str, context: str, details: str, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_lineage_failure for session {session_id}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.lineage_failures.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            context=context,
            details=details,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_trace_failure(self, session_id: str, context: str, details: str, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_trace_failure for session {session_id}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.trace_failures.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            context=context,
            details=details,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_quarantine(self, session_id: str, resource_id: str, reason: str, shadow_tag: Optional[str] = None, event_meta: Dict[str, Any] | None = None) -> None:
        event_meta = event_meta or {}
        if not event_meta or not event_meta.get("event_id"):
            raise IdentityContractViolation(f"Missing event_id in persist_quarantine for session {session_id} resource {resource_id}")
        new_state_str = event_meta.get("event_state")
        if new_state_str:
            new_state = self._state_from_str(new_state_str)
            prev = self._get_last_state(event_meta.get("event_id"))
            if new_state is not None:
                governance_state.validate_transition(prev, new_state)
        ins = self.quarantine.insert().values(
            session_id=session_id,
            timestamp=self._now(),
            event_id=event_meta.get("event_id"),
            parent_event_id=event_meta.get("parent_event_id"),
            root_event_id=event_meta.get("root_event_id"),
            operation_sequence=event_meta.get("operation_sequence"),
            interception_stage=event_meta.get("interception_stage"),
            causal_depth=event_meta.get("causal_depth"),
            operation_hash=event_meta.get("operation_hash"),
            replay_epoch=event_meta.get("replay_epoch"),
            timestamp_ns=event_meta.get("timestamp_ns"),
            resource_id=resource_id,
            reason=reason,
            shadow_tag=shadow_tag,
            event_state=event_meta.get("event_state"),
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def snapshot_metrics(self, session_id: str, metrics: Dict[str, int]) -> None:
        # Simple implementation: write a decision log entry with snapshot payload
        import json

        self.persist_decision(session_id, "METRICS_SNAPSHOT", "INFO", json.dumps(metrics))

    # New: dedicated snapshots table for trend tracking
    def persist_snapshot(self, session_id: str, metrics: Dict[str, Any]) -> None:
        # create table if missing
        from sqlalchemy import Table, Column, Integer, String, DateTime, Text
        snapshot = Table(
            "governance_snapshots",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), index=True),
            Column("timestamp", DateTime),
            Column("payload", Text),
        )
        snapshot.create(bind=self.engine, checkfirst=True)
        ins = snapshot.insert().values(session_id=session_id, timestamp=self._now(), payload=json.dumps(metrics))
        with self.engine.begin() as conn:
            conn.execute(ins)

    def persist_replay_verification(self,
                                   replay_id: str,
                                   canonical_session_id: str,
                                   replay_session_id: str,
                                   root_event_id: str | None,
                                   verification_state: str,
                                   divergence_event_id: str | None,
                                   escalation_decision: str | None,
                                   illegal_transition_count: int | None,
                                   canonical_hash: str | None = None,
                                   replay_hash: str | None = None,
                                   divergence_hash: str | None = None,
                                   segment_hash: str | None = None,
                                   causal_depth: int | None = None,
                                   replay_epoch: int | None = None,
                                   created_at_ns: int | None = None) -> None:
        from sqlalchemy import Table, Column, Integer, String, DateTime, Text
        # create table if missing
        replay = Table(
            "governance_replay_verification_log",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("replay_id", String(64), index=True),
            Column("canonical_session_id", String(64), index=True),
            Column("replay_session_id", String(64), index=True),
            Column("root_event_id", String(64)),
            Column("divergence_event_id", String(64)),
            Column("verification_state", String(32)),
            Column("escalation_decision", String(32)),
            Column("illegal_transition_count", Integer),
            Column("canonical_hash", String(128)),
            Column("replay_hash", String(128)),
            Column("divergence_hash", String(128)),
            Column("segment_hash", String(128)),
            Column("causal_depth", Integer),
            Column("replay_epoch", Integer),
            Column("created_at_ns", Integer),
        )
        replay.create(bind=self.engine, checkfirst=True)
        ins = replay.insert().values(
            replay_id=replay_id,
            canonical_session_id=canonical_session_id,
            replay_session_id=replay_session_id,
            root_event_id=root_event_id,
            divergence_event_id=divergence_event_id,
            verification_state=verification_state,
            escalation_decision=escalation_decision,
            illegal_transition_count=illegal_transition_count,
            canonical_hash=canonical_hash,
            replay_hash=replay_hash,
            divergence_hash=divergence_hash,
            segment_hash=segment_hash,
            causal_depth=causal_depth,
            replay_epoch=replay_epoch,
            created_at_ns=created_at_ns,
        )
        with self.engine.begin() as conn:
            conn.execute(ins)

    def query_latest_snapshot(self, session_id: str):
        from sqlalchemy import Table, select
        snapshot = Table("governance_snapshots", self.metadata, autoload_with=self.engine)
        s = select(snapshot.c.payload).where(snapshot.c.session_id == session_id).order_by(snapshot.c.timestamp.desc()).limit(1)
        with self.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        if not rows:
            return None
        import json

        return json.loads(rows[0][0])

    def query_counts(self, table: Table, session_id: Optional[str] = None) -> int:
        s = select(table.c.id)
        if session_id:
            s = s.where(table.c.session_id == session_id)
        with self.engine.begin() as conn:
            rows = conn.execute(s).fetchall()
        return len(rows)
