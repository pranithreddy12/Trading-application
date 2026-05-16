from __future__ import annotations

import time

from atlas.validation.base_stage import BaseStage
from atlas.validation.models import StageResult, StageStatus, DefectType, Evidence

ENDPOINTS = {
    "GET /health": {"method": "GET", "path": "/health"},
    "GET /copy/logs": {"method": "GET", "path": "/copy/logs"},
    "GET /leaders": {"method": "GET", "path": "/leaders"},
    "GET /followers": {"method": "GET", "path": "/followers"},
    "GET /portfolio": {"method": "GET", "path": "/portfolio"},
    "GET /positions": {"method": "GET", "path": "/positions"},
    "GET /risk": {"method": "GET", "path": "/risk"},
    "GET /strategies": {"method": "GET", "path": "/strategies"},
    "GET /status": {"method": "GET", "path": "/status"},
    "GET /copy/status": {"method": "GET", "path": "/copy/status"},
}


class RouteStage(BaseStage):
    name = "03_route_auth"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        generated_keys = ctx.generated_keys
        import httpx

        admin_key = generated_keys.get("admin", {}).get("raw_key")
        if not admin_key:
            result.status = StageStatus.FAIL
            result.defect = DefectType.AUTH_FAILURE
            result.error = "No admin key available"
            return result

        async with httpx.AsyncClient(base_url=ctx.api_base, timeout=10.0) as client:
            for label, cfg in ENDPOINTS.items():
                status_code, body, latency = await self._request(
                    client, cfg["method"], cfg["path"], admin_key
                )
                if status_code in (200, 201):
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"admin -> {label} -> {status_code}",
                            latency_ms=latency,
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.FAIL,
                            defect=DefectType.AUTH_FAILURE,
                            message=f"admin -> {label} -> {status_code}",
                            latency_ms=latency,
                        )
                    )
                    result.status = StageStatus.FAIL
                    result.defect = DefectType.AUTH_FAILURE

            read_key = generated_keys.get("read_only", {}).get("raw_key")
            if read_key:
                for label, cfg in ENDPOINTS.items():
                    if cfg["method"] == "GET":
                        status_code, body, latency = await self._request(
                            client, cfg["method"], cfg["path"], read_key
                        )
                        if status_code in (200, 201, 403, 429):
                            result.evidence.append(
                                Evidence(
                                    stage=self.name,
                                    status=StageStatus.PASS,
                                    message=f"read_only -> {label} -> {status_code}",
                                    latency_ms=latency,
                                )
                            )
                        else:
                            result.evidence.append(
                                Evidence(
                                    stage=self.name,
                                    status=StageStatus.FAIL,
                                    defect=DefectType.PERMISSION_FAILURE,
                                    message=f"read_only -> {label} -> {status_code}",
                                    latency_ms=latency,
                                )
                            )
        return result

    async def _request(self, client, method: str, path: str, token: str) -> tuple:
        start_t = time.time()
        try:
            resp = await client.request(
                method, path, headers={"Authorization": f"Bearer {token}"}
            )
            latency = (time.time() - start_t) * 1000
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}
            return resp.status_code, body, latency
        except Exception as exc:
            latency = (time.time() - start_t) * 1000
            return 0, {"error": str(exc)}, latency
