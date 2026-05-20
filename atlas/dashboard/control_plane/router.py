"""
Control Plane Router — Operator management endpoints for ATLAS system control.

Endpoints:
  POST /control/pause-agent       — Pause a running agent
  POST /control/resume-agent      — Resume a paused agent
  POST /control/restart-agent     — Restart a failed agent
  POST /control/freeze-capital    — Freeze all capital deployment
  POST /control/release-capital   — Release capital freeze
  POST /control/retire-strategy   — Force-retire a strategy
  GET  /control/agent-status      — Get all agent statuses
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

from atlas.config.settings import settings

control_plane_router = APIRouter(prefix="/control", tags=["Control Plane"])


async def _get_db():
    from atlas.data.storage.timescale_client import TimescaleClient
    db = TimescaleClient(settings.database_url)
    await db.connect()
    return db


async def _get_redis():
    from redis.asyncio import Redis
    return Redis.from_url(settings.redis_url)


@control_plane_router.post("/pause-agent")
async def pause_agent(agent_name: str):
    """Pause a running agent by name."""
    try:
        redis = await _get_redis()
        keys = await redis.keys(f"agent:*")
        found = False
        for key in keys:
            data = await redis.hgetall(key)
            name = None
            for k, v in data.items():
                if k == b"name" or k == "name":
                    name = v.decode() if isinstance(v, bytes) else v
                    break
            if name == agent_name:
                await redis.hset(key, "status", "paused")
                found = True
                break
        await redis.aclose()
        if found:
            return {"status": "paused", "agent": agent_name}
        return {"status": "not_found", "agent": agent_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/resume-agent")
async def resume_agent(agent_name: str):
    """Resume a paused agent."""
    try:
        redis = await _get_redis()
        keys = await redis.keys("agent:*")
        found = False
        for key in keys:
            data = await redis.hgetall(key)
            name = None
            for k, v in data.items():
                if k == b"name" or k == "name":
                    name = v.decode() if isinstance(v, bytes) else v
                    break
            if name == agent_name:
                await redis.hset(key, "status", "running")
                found = True
                break
        await redis.aclose()
        if found:
            return {"status": "resumed", "agent": agent_name}
        return {"status": "not_found", "agent": agent_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/restart-agent")
async def restart_agent(agent_name: str):
    """Signal an agent to restart."""
    try:
        redis = await _get_redis()
        await redis.publish(
            "agent:control",
            json.dumps({"action": "restart", "agent": agent_name}),
        )
        await redis.aclose()
        return {"status": "restart_signaled", "agent": agent_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/freeze-capital")
async def freeze_capital():
    """Freeze all capital deployment."""
    try:
        redis = await _get_redis()
        await redis.set("capital:frozen", "1", ex=3600)
        await redis.aclose()
        return {"status": "capital_frozen"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/release-capital")
async def release_capital():
    """Release capital freeze."""
    try:
        redis = await _get_redis()
        await redis.delete("capital:frozen")
        await redis.aclose()
        return {"status": "capital_released"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/retire-strategy")
async def retire_strategy(strategy_id: str):
    """Force-retire a strategy."""
    try:
        db = await _get_db()
        from sqlalchemy.sql import text
        async with db.engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE strategies
                    SET status = 'retired', updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": strategy_id},
            )
        return {"status": "retired", "strategy_id": strategy_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.get("/agent-status")
async def get_agent_status():
    """Get status of all registered agents."""
    try:
        redis = await _get_redis()
        keys = await redis.keys("agent:*")
        agents = []
        for key in keys:
            data = await redis.hgetall(key)
            agent = {}
            for k, v in data.items():
                key_str = k.decode() if isinstance(k, bytes) else k
                val_str = v.decode() if isinstance(v, bytes) else v
                agent[key_str] = val_str
            agents.append(agent)
        await redis.aclose()
        return {"agents": agents}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@control_plane_router.post("/emergency-mode")
async def trigger_emergency_mode(reason: str = "operator_action"):
    """Trigger emergency risk mode for the entire system."""
    try:
        redis = await _get_redis()
        await redis.hset(
            "kill_switch:state",
            mapping={"active": "1", "reason": f"ControlPlane: {reason}"},
        )
        await redis.aclose()
        return {"status": "emergency_mode_activated", "reason": reason}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
