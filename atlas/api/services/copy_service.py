from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.sql import text

from atlas.api.services.risk_service import RiskService
from atlas.data.storage.timescale_client import TimescaleClient


class CopyService:
    """Service layer for copy domain reads and governance-ready status."""

    def __init__(self, db: TimescaleClient, risk_service: RiskService):
        self.db = db
        self.risk = risk_service

    async def get_copy_logs(self, limit: int = 20, status: Optional[str] = None, symbol: Optional[str] = None) -> dict[str, Any]:
        query = """
            SELECT
                id,
                leader_order_id,
                follower_order_id,
                leader_id,
                follower_id,
                symbol,
                side,
                leader_qty,
                follower_qty,
                latency_ms,
                status,
                failure_reason,
                created_at
            FROM copy_execution_log
            WHERE 1=1
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            query += " AND status = :status"
            params["status"] = status
        if symbol:
            query += " AND symbol = :symbol"
            params["symbol"] = symbol.upper()
        query += " ORDER BY created_at DESC LIMIT :limit"

        async with self.db.engine.connect() as conn:
            result = await conn.execute(text(query), params)
            rows = result.fetchall()

        logs = [
            {
                "id": str(row[0]),
                "leader_order_id": str(row[1]) if row[1] else None,
                "follower_order_id": str(row[2]) if row[2] else None,
                "leader_id": str(row[3]) if row[3] else None,
                "follower_id": str(row[4]) if row[4] else None,
                "symbol": row[5],
                "side": row[6],
                "leader_qty": float(row[7]) if row[7] else 0,
                "follower_qty": float(row[8]) if row[8] else 0,
                "latency_ms": row[9],
                "status": row[10],
                "failure_reason": row[11],
                "created_at": row[12].isoformat() if row[12] else None,
            }
            for row in rows
        ]
        return {"count": len(logs), "logs": logs}

    async def get_leaders(self) -> dict[str, Any]:
        async with self.db.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT leader_id, account_ref, broker, is_active, created_at, metadata
                FROM copy_leader_accounts
                ORDER BY created_at DESC
            """))
            rows = result.fetchall()
        leaders = [
            {
                "leader_id": str(row[0]),
                "account_ref": row[1],
                "broker": row[2],
                "is_active": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "metadata": row[5] or {},
            }
            for row in rows
        ]
        return {"count": len(leaders), "leaders": leaders}

    async def get_followers(self, leader_id: Optional[str] = None) -> dict[str, Any]:
        query = """
            SELECT
                follower_id, leader_id, account_ref, broker, allocation_ratio,
                max_position_pct, is_active, created_at, metadata
            FROM copy_follower_accounts
        """
        params: dict[str, Any] = {}
        if leader_id:
            query += " WHERE leader_id = :leader_id"
            params["leader_id"] = leader_id
        query += " ORDER BY created_at DESC"

        async with self.db.engine.connect() as conn:
            result = await conn.execute(text(query), params)
            rows = result.fetchall()

        followers = [
            {
                "follower_id": str(row[0]),
                "leader_id": str(row[1]),
                "account_ref": row[2],
                "broker": row[3],
                "allocation_ratio": float(row[4]) if row[4] else 1.0,
                "max_position_pct": float(row[5]) if row[5] else 0.1,
                "is_active": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "metadata": row[8] or {},
            }
            for row in rows
        ]
        return {"count": len(followers), "followers": followers}

    async def get_copy_status(self) -> dict[str, Any]:
        async with self.db.engine.connect() as conn:
            filled_count = (await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status = 'filled'"))).scalar() or 0
            failed_count = (await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status = 'failed'"))).scalar() or 0
            avg_latency = (await conn.execute(text("SELECT AVG(latency_ms) FROM copy_execution_log WHERE latency_ms > 0"))).scalar() or 0
            leader_count = (await conn.execute(text("SELECT COUNT(*) FROM copy_leader_accounts WHERE is_active = TRUE"))).scalar() or 0
            follower_count = (await conn.execute(text("SELECT COUNT(*) FROM copy_follower_accounts WHERE is_active = TRUE"))).scalar() or 0
            last_exec_ts = (await conn.execute(text("SELECT MAX(created_at) FROM copy_execution_log"))).scalar()

        running_state = "idle"
        if last_exec_ts:
            age_seconds = (datetime.utcnow() - last_exec_ts.replace(tzinfo=None)).total_seconds() if getattr(last_exec_ts, "tzinfo", None) else (datetime.utcnow() - last_exec_ts).total_seconds()
            running_state = "active" if age_seconds <= 300 else "stale"

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "running_state": running_state,
            "active_leaders": int(leader_count),
            "active_followers": int(follower_count),
            "last_latency_ms": float(avg_latency) if avg_latency else 0.0,
            "failures": int(failed_count),
            "filled_orders": int(filled_count),
            "queue_depth": None,
        }
