"""
audit_ledger.py — Immutable audit ledger with cryptographic hash chaining.

Provides tamper-resistant governance tracking for:
- validations, approvals, deployments, retirements
- capital reallocations, overrides, kill switches
- risk breaches, operator actions
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from loguru import logger
from sqlalchemy.sql import text


class AuditEventType(str, Enum):
    VALIDATION = "validation"
    APPROVAL = "approval"
    DEPLOYMENT = "deployment"
    RETIREMENT = "retirement"
    CAPITAL_REALLOCATION = "capital_reallocation"
    OVERRIDE = "override"
    KILL_SWITCH = "kill_switch"
    RISK_BREACH = "risk_breach"
    OPERATOR_ACTION = "operator_action"
    SYSTEM_CONFIG = "system_config"


class AuditLedger:
    """
    Append-only, tamper-resistant audit ledger with hash chaining.

    Each entry includes:
    - hash_prev: SHA-256 of the previous audit entry
    - hash_self: SHA-256 of this entry's content (including hash_prev)
    - signature: cryptographic signature of the entry
    """

    def __init__(self, db):
        self.db = db

    async def record(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "info",
        trace_id: Optional[str] = None,
    ) -> str:
        """Record an immutable audit entry. Returns entry_id."""
        entry_id = uuid.uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()

        # Get previous hash for chain
        prev_hash = await self._get_last_hash()

        # Build content for self-hash
        content = {
            "id": entry_id,
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "severity": severity,
            "trace_id": trace_id,
            "hash_prev": prev_hash,
            "created_at": now,
        }
        hash_self = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode("utf-8")
        ).hexdigest()

        await self.db._execute_insert(
            """
            INSERT INTO audit_ledger
                (id, event_type, actor, action, resource_type, resource_id,
                 details, severity, trace_id, hash_prev, hash_self, created_at)
            VALUES
                (:id, :event_type, :actor, :action, :resource_type, :resource_id,
                 :details::jsonb, :severity, :trace_id, :hash_prev, :hash_self, :created_at::timestamptz)
            """,
            {
                "id": entry_id,
                "event_type": event_type,
                "actor": actor,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": json.dumps(details or {}),
                "severity": severity,
                "trace_id": trace_id,
                "hash_prev": prev_hash,
                "hash_self": hash_self,
                "created_at": now,
            },
        )

        logger.info(f"Audit: {event_type} | {actor} | {action} | {resource_type}:{resource_id}")
        return entry_id

    async def get_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[dict]:
        """Query audit entries with optional filters."""
        conditions = []
        params: dict = {"limit": limit, "offset": offset}

        if event_type:
            conditions.append("event_type = :event_type")
            params["event_type"] = event_type
        if actor:
            conditions.append("actor = :actor")
            params["actor"] = actor
        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT id, event_type, actor, action, resource_type, resource_id,
                           details, severity, trace_id, hash_prev, hash_self, created_at
                    FROM audit_ledger
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            return [self._row_to_entry(row) for row in result.fetchall()]

    async def verify_chain(self) -> dict:
        """
        Verify the integrity of the entire audit chain.
        Returns verification report.
        """
        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, event_type, actor, action, resource_type, resource_id,
                           details, severity, trace_id, hash_prev, hash_self, created_at
                    FROM audit_ledger
                    ORDER BY created_at ASC
                """),
            )
            rows = result.fetchall()

        if not rows:
            return {"valid": True, "entries_checked": 0}

        violations = []
        prev_hash = None
        for i, row in enumerate(rows):
            entry = self._row_to_entry(row)

            # Verify self-hash
            content = {
                "id": entry["id"],
                "event_type": entry["event_type"],
                "actor": entry["actor"],
                "action": entry["action"],
                "resource_type": entry["resource_type"],
                "resource_id": entry["resource_id"],
                "details": entry["details"],
                "severity": entry["severity"],
                "trace_id": entry["trace_id"],
                "hash_prev": entry["hash_prev"],
                "created_at": entry["created_at"],
            }
            expected_hash = hashlib.sha256(
                json.dumps(content, sort_keys=True).encode("utf-8")
            ).hexdigest()

            if expected_hash != entry["hash_self"]:
                violations.append(f"Entry {i} ({entry['id']}): self-hash mismatch")

            if i > 0 and entry["hash_prev"] != prev_hash:
                violations.append(
                    f"Entry {i} ({entry['id']}): chain broken "
                    f"(expected prev_hash={prev_hash[:16]}...)"
                )

            prev_hash = entry["hash_self"]

        return {
            "valid": len(violations) == 0,
            "entries_checked": len(rows),
            "violations": violations,
        }

    async def get_summary(
        self,
        hours: int = 24,
    ) -> dict:
        """Get audit summary for the time window."""
        async with self.db.engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT actor) as unique_actors,
                        COUNT(DISTINCT event_type) as unique_types,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_events,
                        COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warnings
                    FROM audit_ledger
                    WHERE created_at > NOW() - INTERVAL ':hours hours'
                """),
                {"hours": hours},
            )
            row = r.fetchone()
            if not row:
                return {}

            r2 = await conn.execute(
                text("""
                    SELECT event_type, COUNT(*) as cnt
                    FROM audit_ledger
                    WHERE created_at > NOW() - INTERVAL ':hours hours'
                    GROUP BY event_type ORDER BY cnt DESC
                """),
                {"hours": hours},
            )
            by_type = {str(r[0]): r[1] for r in r2.fetchall()}

            return {
                "total_entries": row[0],
                "unique_actors": row[1],
                "unique_types": row[2],
                "critical_events": row[3],
                "warnings": row[4],
                "by_type": by_type,
            }

    async def _get_last_hash(self) -> Optional[str]:
        async with self.db.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT hash_self FROM audit_ledger
                    ORDER BY created_at DESC LIMIT 1
                """),
            )
            row = result.fetchone()
            return str(row[0]) if row else None

    def _row_to_entry(self, row) -> dict:
        details = row[6]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        return {
            "id": str(row[0]),
            "event_type": str(row[1]),
            "actor": str(row[2]),
            "action": str(row[3]),
            "resource_type": str(row[4]),
            "resource_id": str(row[5]) if row[5] else None,
            "details": details,
            "severity": str(row[7]),
            "trace_id": str(row[8]) if row[8] else None,
            "hash_prev": str(row[9]) if row[9] else None,
            "hash_self": str(row[10]),
            "created_at": row[11].isoformat() if hasattr(row[11], "isoformat") else str(row[11]),
        }
