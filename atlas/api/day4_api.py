"""
Day 4 Authenticated REST API

Purpose:
  - Expose operational copy trading system
  - Read-first endpoints (write APIs in Day 5)
  - Bearer token authentication
  - <500ms latency target

Endpoints:
  - GET /health — System status
  - GET /copy/logs — Copy execution history
  - GET /leaders — Leader accounts
  - GET /followers — Follower subscriptions
  - GET /portfolio — Portfolio balances (optional)
  - GET /positions — Open positions (optional)
  - GET /risk — Portfolio risk metrics (optional)

Usage:
  uvicorn atlas.api.day4_api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import text
import time
from typing import Optional
from datetime import datetime
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from loguru import logger

from atlas.api.middleware.auth_middleware import (
    AuthMiddleware,
    set_auth_middleware,
    verify_token,
    verify_admin_token,
    verify_trader_token,
    verify_read_token,
)
from atlas.api.routes.copy_status import router as copy_status_router
from atlas.api.services.auth_service import APIKey, AuthService
from atlas.api.services.copy_service import CopyService
from atlas.api.services.health_service import HealthService
from atlas.api.services.rate_limit_service import RateLimitService
from atlas.api.services.risk_service import RiskService

# Initialize FastAPI app
app = FastAPI(
    title="ATLAS Day 4 API",
    description="Authenticated copy trading and portfolio management API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_requests(request: Request, call_next):
    start = time.time()
    status_code = 500
    error_message = None
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        if auth_middleware:
            latency_ms = int((time.time() - start) * 1000)
            try:
                await auth_middleware.log_request(
                    request=request,
                    response_status=status_code,
                    latency_ms=latency_ms,
                    error_message=error_message,
                )
            except Exception as log_exc:
                logger.warning(f"Request audit logging failed: {log_exc}")

    return response

# Database and governance services (lazy-loaded)
db_client = None
auth_service: Optional[AuthService] = None
auth_middleware: Optional[AuthMiddleware] = None
rate_limit_service: Optional[RateLimitService] = None
copy_service: Optional[CopyService] = None
health_service: Optional[HealthService] = None
risk_service: Optional[RiskService] = None


async def get_db() -> TimescaleClient:
    """Lazy-load database client."""
    global db_client
    if db_client is None:
        db_client = TimescaleClient(settings.database_url)
        await db_client.connect()
    return db_client


async def _enforce_governance(request: Request, api_key: APIKey) -> dict[str, str]:
    if not auth_middleware:
        raise HTTPException(status_code=500, detail="Auth middleware not initialized")
    if not rate_limit_service:
        raise HTTPException(status_code=500, detail="Rate limiter not initialized")

    await auth_middleware.verify_scope(request, api_key, request.url.path, request.method)
    decision = await rate_limit_service.check_and_consume(api_key)
    headers = RateLimitService.build_headers(decision)
    if not decision.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)
    request.state.rate_limit_headers = headers
    return headers


def _response(content: dict, request: Request, status_code: int = 200) -> JSONResponse:
    headers = getattr(request.state, "rate_limit_headers", {})
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def verify_read_access(request: Request, api_key: APIKey = Depends(verify_read_token)) -> APIKey:
    await _enforce_governance(request, api_key)
    return api_key


async def verify_trader_access(request: Request, api_key: APIKey = Depends(verify_trader_token)) -> APIKey:
    await _enforce_governance(request, api_key)
    return api_key


async def verify_admin_access(request: Request, api_key: APIKey = Depends(verify_admin_token)) -> APIKey:
    await _enforce_governance(request, api_key)
    return api_key


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global auth_service, auth_middleware, rate_limit_service, copy_service, health_service, risk_service

    logger.info("Day 4 API starting...")
    db = await get_db()
    auth_service = AuthService(db)
    auth_middleware = AuthMiddleware(auth_service)
    rate_limit_service = RateLimitService(getattr(settings, "redis_url", None))
    risk_service = RiskService()
    copy_service = CopyService(db, risk_service)
    health_service = HealthService(db, getattr(rate_limit_service, "redis", None))
    set_auth_middleware(auth_middleware)

    app.state.auth_middleware = auth_middleware
    app.state.rate_limit_service = rate_limit_service
    app.state.copy_service = copy_service

    logger.info("Database connection established")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global db_client
    if db_client:
        logger.info("Shutting down database connection")
        db_client = None


@app.get("/health", tags=["Health"])
async def health(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """
    System health status.
    
    Returns operational status of copy trader, database, and Redis.
    """
    start = time.time()
    
    try:
        if not health_service:
            raise HTTPException(status_code=500, detail="Health service unavailable")
        payload = await health_service.get_health()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")
    
    latency_ms = int((time.time() - start) * 1000)
    
    payload["latency_ms"] = latency_ms
    payload["version"] = "1.0.0"
    return _response(payload, request)


@app.get("/copy/logs", tags=["Copy Trading"])
async def get_copy_logs(
    request: Request,
    api_key: APIKey = Depends(verify_read_access),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: filled, skipped, failed"),
    symbol: Optional[str] = Query(None, description="Filter by symbol")
):
    """
    Get copy execution history.
    
    Returns recent copy execution audit trail with filtering options.
    """
    start = time.time()
    
    try:
        if not copy_service:
            raise HTTPException(status_code=500, detail="Copy service unavailable")
        payload = await copy_service.get_copy_logs(limit=limit, status=status, symbol=symbol)
        
        latency_ms = int((time.time() - start) * 1000)
        
        payload["latency_ms"] = latency_ms
        return _response(payload, request)
    
    except Exception as e:
        logger.error(f"Error fetching copy logs: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching copy logs: {str(e)}")


@app.get("/leaders", tags=["Leaders"])
async def get_leaders(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """
    List active leader accounts.
    
    Returns all configured leader accounts and their status.
    """
    start = time.time()
    
    try:
        if not copy_service:
            raise HTTPException(status_code=500, detail="Copy service unavailable")
        payload = await copy_service.get_leaders()
        
        latency_ms = int((time.time() - start) * 1000)
        
        payload["latency_ms"] = latency_ms
        return _response(payload, request)
    
    except Exception as e:
        logger.error(f"Error fetching leaders: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching leaders: {str(e)}")


@app.get("/followers", tags=["Followers"])
async def get_followers(
    request: Request,
    api_key: APIKey = Depends(verify_read_access),
    leader_id: Optional[str] = Query(None, description="Filter by leader_id")
):
    """
    List active follower accounts.
    
    Returns all configured follower accounts with allocation ratios and limits.
    """
    start = time.time()
    
    try:
        if not copy_service:
            raise HTTPException(status_code=500, detail="Copy service unavailable")
        payload = await copy_service.get_followers(leader_id=leader_id)
        
        latency_ms = int((time.time() - start) * 1000)
        
        payload["latency_ms"] = latency_ms
        return _response(payload, request)
    
    except Exception as e:
        logger.error(f"Error fetching followers: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching followers: {str(e)}")


@app.get("/portfolio", tags=["Portfolio"])
async def get_portfolio(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """
    Portfolio summary (placeholder for Day 4).
    
    Returns aggregate portfolio data (implemented in Day 5 with full position tracking).
    """
    start = time.time()
    
    return _response(
        {
            "status": "placeholder",
            "message": "Full portfolio tracking available in Day 5",
            "leaders": {
                "total": 0,
                "active": 0
            },
            "followers": {
                "total": 0,
                "active": 0
            },
            "latency_ms": int((time.time() - start) * 1000)
        },
        request
    )


@app.get("/positions", tags=["Portfolio"])
async def get_positions(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """Open positions snapshot (best effort, schema-optional)."""
    start = time.time()
    try:
        db = await get_db()
        async with db.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT account_ref, symbol, qty
                FROM positions
                ORDER BY symbol, account_ref
                LIMIT 200
            """))
            rows = result.fetchall()
        positions = [
            {
                "account_ref": row[0],
                "symbol": row[1],
                "qty": float(row[2]) if row[2] is not None else 0.0,
            }
            for row in rows
        ]
    except Exception:
        positions = []

    return _response(
        {
            "count": len(positions),
            "positions": positions,
            "latency_ms": int((time.time() - start) * 1000),
        },
        request,
    )


@app.get("/risk", tags=["Risk"])
async def get_risk(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """
    Portfolio risk metrics (placeholder for Day 4).
    
    Returns risk calculations and warnings (full implementation in Day 5).
    """
    start = time.time()
    
    if not risk_service:
        raise HTTPException(status_code=500, detail="Risk service unavailable")
    payload = await risk_service.get_risk_snapshot()
    payload["latency_ms"] = int((time.time() - start) * 1000)
    return _response(payload, request)


@app.get("/strategies", tags=["Strategies"])
async def get_strategies(
    request: Request,
    api_key: APIKey = Depends(verify_read_access),
    status: Optional[str] = Query(None, description="Filter by status: elite, validated, research_candidate"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    List validated strategies (read-only).
    
    Returns strategies from validator agent with Day-4 metrics.
    """
    start = time.time()
    
    try:
        db = await get_db()
        
        query = """
            SELECT 
                id,
                name,
                author_agent,
                status,
                validation_metrics,
                created_at
            FROM strategies
            WHERE status IS NOT NULL
        """
        
        params = {}
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit
        
        async with db.engine.connect() as conn:
            result = await conn.execute(text(query), params)
            rows = result.fetchall()
        
        strategies = [
            {
                "id": str(row[0]),
                "name": row[1],
                "author_agent": row[2],
                "status": row[3],
                "validation_metrics": row[4] or {},
                "created_at": row[5].isoformat() if row[5] else None
            }
            for row in rows
        ]
        
        latency_ms = int((time.time() - start) * 1000)
        
        return _response(
            {
                "count": len(strategies),
                "strategies": strategies,
                "latency_ms": latency_ms
            },
            request
        )
    
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching strategies: {str(e)}")


@app.get("/status", tags=["Status"])
async def get_status(request: Request, api_key: APIKey = Depends(verify_read_access)):
    """
    Comprehensive system status.
    
    Returns copy trader operational status, recent executions, and system metrics.
    """
    start = time.time()
    
    try:
        db = await get_db()
        
        # Count copy executions
        async with db.engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status = 'filled'"))
            filled_count = result.scalar()
            
            result = await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE status = 'skipped'"))
            skipped_count = result.scalar()
            
            result = await conn.execute(text("SELECT AVG(latency_ms) FROM copy_execution_log WHERE latency_ms > 0"))
            avg_latency = result.scalar()
            
            result = await conn.execute(text("SELECT COUNT(*) FROM copy_leader_accounts WHERE is_active = TRUE"))
            leader_count = result.scalar()
            
            result = await conn.execute(text("SELECT COUNT(*) FROM copy_follower_accounts WHERE is_active = TRUE"))
            follower_count = result.scalar()
        
        latency_ms = int((time.time() - start) * 1000)
        
        return _response(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "copy_trader": {
                    "status": "operational",
                    "filled_orders": filled_count or 0,
                    "skipped_orders": skipped_count or 0,
                    "avg_latency_ms": float(avg_latency) if avg_latency else 0
                },
                "accounts": {
                    "leaders": leader_count or 0,
                    "followers": follower_count or 0
                },
                "latency_ms": latency_ms
            },
            request
        )
    
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching status: {str(e)}")


app.include_router(copy_status_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
