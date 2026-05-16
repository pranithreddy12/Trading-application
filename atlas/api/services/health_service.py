from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.sql import text

from atlas.data.storage.timescale_client import TimescaleClient


class HealthService:
    """Operational health snapshot for API, DB, Redis, and agents."""

    def __init__(self, db: TimescaleClient, redis_client: Any = None):
        self.db = db
        self.redis = redis_client

    async def _db_status(self) -> str:
        try:
            async with self.db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return "connected"
        except Exception:
            return "disconnected"

    async def _redis_status(self) -> str:
        if not self.redis:
            return "unavailable"
        try:
            pong = await self.redis.ping()
            return "connected" if pong else "degraded"
        except Exception:
            return "disconnected"

    async def _agent_status(self) -> dict[str, Any]:
        result = {
            "copy_trader": {"status": "unknown", "last_heartbeat": None},
            "validator": {"status": "unknown", "last_heartbeat": None},
        }
        if not self.redis:
            return result

        now = datetime.now(timezone.utc)
        async for key in self.redis.scan_iter(match="agent:*"):
            data = await self.redis.hgetall(key)
            if not data:
                continue
            agent_type = data.get("agent_type")
            status = data.get("status")
            ttl = await self.redis.ttl(key)
            heartbeat = (now.timestamp() + ttl) if ttl and ttl > 0 else None
            mapped = {
                "status": status or "unknown",
                "last_heartbeat": datetime.fromtimestamp(heartbeat, tz=timezone.utc).isoformat() if heartbeat else None,
            }
            if agent_type == "copy_trader":
                result["copy_trader"] = mapped
            if agent_type == "validator":
                result["validator"] = mapped
        return result

    async def get_health(self) -> dict[str, Any]:
        db_status = await self._db_status()
        redis_status = await self._redis_status()
        agents = await self._agent_status()

        overall = "healthy"
        if db_status != "connected":
            overall = "critical"
        elif redis_status not in ("connected", "unavailable"):
            overall = "degraded"

        return {
            "status": overall,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "api": "operational",
                "db": db_status,
                "redis": redis_status,
                "copy_trader": agents["copy_trader"]["status"],
                "validator": agents["validator"]["status"],
            },
            "last_heartbeat": {
                "copy_trader": agents["copy_trader"]["last_heartbeat"],
                "validator": agents["validator"]["last_heartbeat"],
            },
        }
