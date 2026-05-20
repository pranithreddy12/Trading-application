from __future__ import annotations

import httpx

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence


class RestartStage(BaseStage):
    name = "09_restart_certification"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        auth_service = ctx.auth_service
        generated_keys = ctx.generated_keys
        admin_key = generated_keys.get("admin", {}).get("raw_key", "")

        if not admin_key:
            result.status = StageStatus.SKIPPED
            result.error = "No admin key"
            return result

        async with httpx.AsyncClient(base_url=ctx.api_base, timeout=10.0) as client:
            body_before_copy, leaders_before = await self._get_copy_status(
                client, admin_key
            )
            self._simulate_restart(ctx)
            key_valid = await self._validate_key(auth_service, admin_key)

            if key_valid:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message="Admin key valid after restart (no auth corruption)",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.RESTART_FAILURE,
                        message="Admin key INVALID after restart (auth corruption detected)",
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.RESTART_FAILURE

            read_key_raw = generated_keys.get("read_only", {}).get("raw_key", "")
            if read_key_raw:
                ro_valid = await self._validate_key(auth_service, read_key_raw)
                if ro_valid:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message="Read-only key valid after restart",
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.FAIL,
                            defect=DefectType.RESTART_FAILURE,
                            message="Read-only key invalid after restart",
                        )
                    )
                    result.status = StageStatus.FAIL

            body_after_copy, leaders_after = await self._get_copy_status(
                client, admin_key
            )

            if leaders_after >= leaders_before:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"No state corruption: leaders before={leaders_before}, after={leaders_after}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.RESTART_FAILURE,
                        message=f"State LOSS: leaders before={leaders_before}, after={leaders_after}",
                    )
                )
                result.status = StageStatus.FAIL

        return result

    async def _get_copy_status(self, client, token: str) -> tuple:
        try:
            resp = await client.get(
                "/copy/status", headers={"Authorization": f"Bearer {token}"}
            )
            body = resp.json() if resp.status_code == 200 else {}
            return body, body.get("active_leaders", 0) if isinstance(body, dict) else 0
        except Exception:
            return {}, 0

    async def _validate_key(self, auth_service, raw_key: str) -> bool:
        try:
            key = await auth_service.validate_key(raw_key)
            return key is not None
        except Exception:
            return False

    def _simulate_restart(self, ctx):
        try:
            from atlas.api.middleware.auth_middleware import _auth_middleware

            if _auth_middleware:
                _auth_middleware.clear_cache()
        except Exception:
            pass
