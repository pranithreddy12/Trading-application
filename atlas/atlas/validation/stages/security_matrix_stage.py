from __future__ import annotations

import time
import traceback
from typing import Optional

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence

ENDPOINTS = [
    {"label": "GET /health", "method": "GET", "path": "/health"},
    {"label": "GET /copy/logs", "method": "GET", "path": "/copy/logs"},
    {"label": "GET /leaders", "method": "GET", "path": "/leaders"},
    {"label": "GET /followers", "method": "GET", "path": "/followers"},
    {"label": "GET /copy/status", "method": "GET", "path": "/copy/status"},
]
ROLES = ["admin", "read_only", "revoked", "invalid"]


class SecurityMatrixStage(BaseStage):
    name = "07_security_matrix"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        import httpx

        auth_service = ctx.auth_service
        generated_keys = ctx.generated_keys
        from atlas.api.services.auth_service import APIRole

        admin_key = generated_keys.get("admin", {}).get("raw_key", "")
        read_only_key = generated_keys.get("read_only", {}).get("raw_key", "")
        revoked_key_raw = generated_keys.get("revoked", {}).get("raw_key")

        if not revoked_key_raw:
            try:
                revoked_key_raw, revoked_key_id = await auth_service.generate_api_key(
                    user_id="revoked_test",
                    role=APIRole.READ_ONLY,
                    created_by="live_validation",
                    description="Will be revoked for security matrix test",
                    expires_in_days=1,
                )
                await auth_service.revoke_key(
                    revoked_key_id, "live_validation", "Security matrix test"
                )
            except Exception as exc:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.ERROR,
                        defect=DefectType.AUTH_FAILURE,
                        message=f"Failed to create/revoke test key: {exc}",
                        traceback_str=traceback.format_exc(),
                    )
                )

        invalid_key = "atlas_invalid_key_that_does_not_exist_12345"
        matrix = {}

        async with httpx.AsyncClient(base_url=ctx.api_base, timeout=10.0) as client:
            for role in ROLES:
                matrix[role] = {}
                for ep in ENDPOINTS:
                    token = self._get_token(
                        role,
                        admin_key,
                        read_only_key,
                        revoked_key_raw or "",
                        invalid_key,
                    )
                    status_code, body, latency = await self._request(
                        client, ep["method"], ep["path"], token
                    )
                    matrix[role][ep["label"]] = self._classify_status(status_code)

        for ep in ENDPOINTS:
            val = matrix.get("admin", {}).get(ep["label"], "")
            if val == "PASS":
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"admin -> {ep['label']} -> {val}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.PERMISSION_FAILURE,
                        message=f"admin -> {ep['label']} -> {val} (expected PASS)",
                    )
                )
                result.status = StageStatus.FAIL

        for ep in ENDPOINTS:
            val = matrix.get("revoked", {}).get(ep["label"], "")
            if val in ("UNAUTHORIZED", "FORBIDDEN"):
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"revoked -> {ep['label']} -> {val}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.PERMISSION_FAILURE,
                        message=f"revoked -> {ep['label']} -> {val} (expected 401/403)",
                    )
                )
                result.status = StageStatus.FAIL

        for ep in ENDPOINTS:
            val = matrix.get("invalid", {}).get(ep["label"], "")
            if val == "UNAUTHORIZED":
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"invalid -> {ep['label']} -> {val}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.PERMISSION_FAILURE,
                        message=f"invalid -> {ep['label']} -> {val} (expected UNAUTHORIZED)",
                    )
                )
                result.status = StageStatus.FAIL

        ctx.security_matrix = matrix
        return result

    def _get_token(
        self, role: str, admin: str, read_only: str, revoked: str, invalid: str
    ) -> str:
        return {
            "admin": admin,
            "read_only": read_only,
            "revoked": revoked,
            "invalid": invalid,
        }.get(role, "")

    def _classify_status(self, code: int) -> str:
        if code in (200, 201):
            return "PASS"
        elif code == 403:
            return "FORBIDDEN"
        elif code == 401:
            return "UNAUTHORIZED"
        elif code == 429:
            return "RATE_LIMITED"
        return f"HTTP_{code}"

    async def _request(self, client, method: str, path: str, token: str) -> tuple:
        start_t = time.time()
        try:
            resp = await client.request(
                method, path, headers={"Authorization": f"Bearer {token}"}
            )
            return resp.status_code, {}, (time.time() - start_t) * 1000
        except Exception:
            return 0, {}, (time.time() - start_t) * 1000
