from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from atlas.api.middleware.auth_middleware import verify_token
from atlas.api.services.auth_service import APIKey
from atlas.api.services.rate_limit_service import RateLimitService

router = APIRouter(tags=["Copy Trading"])


@router.get("/copy/status")
async def copy_status(request: Request, api_key: APIKey = Depends(verify_token)):
    start = time.time()

    auth = getattr(request.app.state, "auth_middleware", None)
    if not auth:
        raise HTTPException(status_code=500, detail="Auth middleware unavailable")

    await auth.verify_scope(request, api_key, "/copy/status", "GET")

    limiter = getattr(request.app.state, "rate_limit_service", None)
    if not limiter:
        raise HTTPException(status_code=500, detail="Rate limiter unavailable")

    decision = await limiter.check_and_consume(api_key)
    headers = RateLimitService.build_headers(decision)
    if not decision.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)

    service = getattr(request.app.state, "copy_service", None)
    if not service:
        raise HTTPException(status_code=500, detail="Copy service unavailable")

    payload = await service.get_copy_status()
    payload["latency_ms"] = int((time.time() - start) * 1000)
    return JSONResponse(status_code=200, content=payload, headers=headers)
