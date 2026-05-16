from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import time
from typing import List, Dict, Any
import redis.asyncio as redis
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l4_risk.kill_switch import KillSwitch

# Dummy connection details, normally loaded from settings
REDIS_URL = "redis://localhost:6379"
DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas"

app = FastAPI(title="ATLAS Dashboard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

redis_client = redis.from_url(REDIS_URL)
db_client = TimescaleClient(DB_URL)

@app.on_event("startup")
async def startup_event():
    try:
        await db_client.connect()
    except Exception:
        pass

@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()

@app.get("/health")
async def get_health():
    kill_switch = await KillSwitch.is_active(redis_client)
    return {
        "status": "ok",
        "agents_alive": 5,
        "agents_dead": 0,
        "kill_switch_active": kill_switch,
        "timestamp": int(time.time())
    }

@app.get("/agents")
async def get_agents():
    return [
        {"id": "1", "name": "EquityIngestor", "layer": "L1", "status": "running", "last_heartbeat": "2026-05-12T10:00:00Z", "uptime": 3600}
    ]

@app.get("/strategies")
async def get_strategies(status: str = Query(None), page: int = Query(1), limit: int = Query(20)):
    return {
        "page": page,
        "total": 1,
        "items": [{"id": "s1", "name": "SMA_Crossover", "status": "validated", "sharpe": 1.5, "created_at": "2026-05-12T10:00:00Z"}]
    }

@app.get("/strategies/{id}")
async def get_strategy(id: str):
    return {"id": id, "spec": {}, "code": "", "backtest_results": {}, "paper_trade_summary": {}}

@app.get("/portfolio")
async def get_portfolio():
    return {
        "total_value": 100000.0,
        "cash": 95000.0,
        "invested": 5000.0,
        "total_pnl": 500.0,
        "daily_pnl": 100.0,
        "drawdown": 0.05,
        "open_positions": [{"symbol": "AAPL", "side": "buy", "qty": 10, "entry_price": 150.0, "current_pnl": 50.0}]
    }

@app.get("/paper_trades")
async def get_paper_trades():
    return [{"strategy_name": "SMA_Crossover", "symbol": "AAPL", "pnl": 50.0}]

@app.get("/features/{symbol}")
async def get_features(symbol: str):
    return {"symbol": symbol, "timestamp": int(time.time()), "features": {"rsi_14": 55.5}}

@app.get("/risk")
async def get_risk():
    kill_switch = await KillSwitch.is_active(redis_client)
    return {
        "kill_switch_active": kill_switch,
        "daily_loss_pct": 0.5,
        "weekly_loss_pct": 1.0,
        "drawdown_pct": 2.0,
        "open_positions": 1,
        "limits": {"max_drawdown": 5.0}
    }

@app.get("/system/logs")
async def get_system_logs():
    return [{"timestamp": int(time.time()), "agent_id": "1", "level": "INFO", "message": "Started"}]

@app.get("/intelligence/brief")
async def get_brief():
    return {"text": "Market is trending up. Agents are active.", "timestamp": int(time.time())}

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
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
