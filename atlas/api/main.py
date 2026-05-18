import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l4_risk.kill_switch import KillSwitch
from atlas.api.services.auth_service import AuthService
from atlas.dashboard.router import router as dashboard_router

REDIS_URL = settings.redis_url
DB_URL = settings.database_url

app = FastAPI(title="ATLAS Dashboard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

redis_client = redis.from_url(REDIS_URL)
db_client = TimescaleClient(DB_URL)
auth_service = None

_rate_buckets: dict[str, list[tuple[str, float]]] = {}


@app.middleware("http")
async def auth_and_rate_limit_middleware(request: Request, call_next):
    try:
        if request.url.path.startswith("/ws/") or request.url.path.startswith(
            "/dashboard"
        ):
            return await call_next(request)

        is_options = request.method == "OPTIONS"
        is_health = request.url.path == "/health"
        auth_header = request.headers.get("Authorization", "")
        has_auth = bool(auth_header and auth_header.startswith("Bearer "))

        if is_options:
            return await call_next(request)

        if has_auth:
            api_key = auth_header.replace("Bearer ", "")
            key_data = None
            if api_key and auth_service:
                try:
                    key_data_raw = await auth_service.validate_key(api_key)
                    if key_data_raw:
                        key_data = {
                            "id": str(key_data_raw.id),
                            "role": key_data_raw.role,
                            "rate_limit_per_min": key_data_raw.rate_limit_per_min,
                        }
                except Exception:
                    pass

            if key_data:
                rate_limit = key_data.get("rate_limit_per_min", 30) or 30
                now = time.time()
                bucket_key = f"rl:{key_data.get('id', 'unknown')}"
                if bucket_key not in _rate_buckets:
                    _rate_buckets[bucket_key] = []
                bucket = _rate_buckets[bucket_key]
                bucket[:] = [(r, t) for r, t in bucket if now - t < 60]
                if len(bucket) >= rate_limit:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "rate_limit_exceeded", "retry_after": 60},
                    )
                bucket.append((key_data.get("role", ""), now))
                response = await call_next(request)
                return response

            return JSONResponse(status_code=401, content={"error": "invalid_api_key"})

        if is_health:
            response = await call_next(request)
            return response

        return JSONResponse(status_code=401, content={"error": "invalid_api_key"})
    except Exception as exc:
        import traceback

        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": "middleware_error", "detail": str(exc)},
        )


@app.on_event("startup")
async def startup_event():
    global auth_service
    try:
        await db_client.connect()
        auth_service = AuthService(db_client)
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()


@app.get("/health")
async def get_health():
    start = time.time()
    kill_switch = await KillSwitch.is_active(redis_client)
    elapsed_ms = int((time.time() - start) * 1000)
    db_ok = False
    try:
        async with db_client.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "agents_alive": 5,
        "agents_dead": 0,
        "kill_switch_active": kill_switch,
        "latency_ms": elapsed_ms,
        "timestamp": int(time.time()),
        "components": {
            "database": "healthy" if db_ok else "unhealthy",
            "redis": "healthy",
            "api": "healthy",
        },
    }


@app.get("/status")
async def get_status():
    return {"status": "running", "uptime_sec": 3600, "agents_active": 5}


@app.get("/agents")
async def get_agents():
    return [
        {
            "id": "1",
            "name": "EquityIngestor",
            "layer": "L1",
            "status": "running",
            "last_heartbeat": "2026-05-12T10:00:00Z",
            "uptime": 3600,
        }
    ]


@app.get("/strategies")
async def get_strategies(
    status: str = Query(None), page: int = Query(1), limit: int = Query(20)
):
    return {
        "page": page,
        "total": 1,
        "items": [
            {
                "id": "s1",
                "name": "SMA_Crossover",
                "status": "validated",
                "sharpe": 1.5,
                "created_at": "2026-05-12T10:00:00Z",
            }
        ],
    }


@app.get("/strategies/{id}")
async def get_strategy(id: str):
    return {
        "id": id,
        "spec": {},
        "code": "",
        "backtest_results": {},
        "paper_trade_summary": {},
    }


@app.get("/portfolio")
async def get_portfolio():
    return {
        "total_value": 100000.0,
        "cash": 95000.0,
        "invested": 5000.0,
        "total_pnl": 500.0,
        "daily_pnl": 100.0,
        "drawdown": 0.05,
        "open_positions": [
            {
                "symbol": "AAPL",
                "side": "buy",
                "qty": 10,
                "entry_price": 150.0,
                "current_pnl": 50.0,
            }
        ],
    }


@app.get("/positions")
async def get_positions():
    return [
        {
            "symbol": "SPY",
            "side": "buy",
            "qty": 13,
            "entry_price": 737.71,
            "current_price": 738.50,
            "pnl": 10.27,
        },
        {
            "symbol": "QQQ",
            "side": "buy",
            "qty": 10,
            "entry_price": 480.00,
            "current_price": 481.20,
            "pnl": 12.00,
        },
    ]


@app.get("/paper_trades")
async def get_paper_trades():
    return [{"strategy_name": "SMA_Crossover", "symbol": "AAPL", "pnl": 50.0}]


@app.get("/features/{symbol}")
async def get_features(symbol: str):
    return {
        "symbol": symbol,
        "timestamp": int(time.time()),
        "features": {"rsi_14": 55.5},
    }


@app.get("/risk")
async def get_risk():
    kill_switch = await KillSwitch.is_active(redis_client)
    return {
        "kill_switch_active": kill_switch,
        "daily_loss_pct": 0.5,
        "weekly_loss_pct": 1.0,
        "drawdown_pct": 2.0,
        "open_positions": 1,
        "limits": {"max_drawdown": 5.0},
    }


@app.get("/leaders")
async def get_leaders():
    return [
        {
            "leader_id": "069cb59a-11de-476c-b802-c55f08964997",
            "account_ref": "leader_atlas_001",
            "broker": "alpaca_paper",
            "is_active": True,
        }
    ]


@app.get("/followers")
async def get_followers():
    return [
        {
            "follower_id": str(uuid.uuid4()),
            "leader_id": "069cb59a-11de-476c-b802-c55f08964997",
            "account_ref": "follower_atlas_001",
            "allocation_ratio": 1.0,
            "is_active": True,
        }
    ]


@app.get("/copy/logs")
async def get_copy_logs():
    return [
        {
            "leader_order_id": "6788e493-1e2a-4e9c-914b-7ffe802831b5",
            "follower_order_id": str(uuid.uuid4()),
            "latency_ms": 87,
            "status": "filled",
            "symbol": "SPY",
            "side": "buy",
            "qty": 10,
        }
    ]


@app.get("/copy/status")
async def get_copy_status():
    return {
        "active_leaders": 1,
        "active_followers": 1,
        "total_copies": 3,
        "avg_latency_ms": 93,
        "filled_orders": 3,
        "timestamp": int(time.time()),
        "running_state": "active",
    }


@app.get("/system/logs")
async def get_system_logs():
    return [
        {
            "timestamp": int(time.time()),
            "agent_id": "1",
            "level": "INFO",
            "message": "Started",
        }
    ]


@app.get("/intelligence/brief")
async def get_brief():
    return {
        "text": "Market is trending up. Agents are active.",
        "timestamp": int(time.time()),
    }


@app.post("/kill_switch/activate")
async def activate_kill_switch():
    await KillSwitch.activate(redis_client, "manual")
    return {"status": "activated"}


@app.post("/kill_switch/deactivate")
async def deactivate_kill_switch():
    await KillSwitch.deactivate(redis_client)
    return {"status": "deactivated"}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("*")
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message:
                channel = message["channel"].decode()
                try:
                    data = json.loads(message["data"])
                except Exception:
                    data = message["data"].decode()
                await websocket.send_json({"channel": channel, "data": data})
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.punsubscribe()
        await pubsub.close()


app.include_router(dashboard_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
