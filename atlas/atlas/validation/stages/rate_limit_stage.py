from __future__ import annotations

import time
import traceback

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence


class RateLimitStage(BaseStage):
    name = "04_rate_limiting"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        auth_service = ctx.auth_service
        import httpx

        from atlas.api.services.auth_service import APIRole

        try:
            raw_key, key_id = await auth_service.generate_api_key(
                user_id="rate_limit_test",
                role=APIRole.READ_ONLY,
                created_by="live_validation",
                description="Rate limit test key (2/min)",
                expires_in_days=1,
                rate_limit_per_min=2,
            )

            hit_429 = False
            async with httpx.AsyncClient(base_url=ctx.api_base, timeout=10.0) as client:
                for i in range(5):
                    status_code, body, latency = await self._request(client, raw_key)
                    if status_code == 429:
                        hit_429 = True
                        result.evidence.append(
                            Evidence(
                                stage=self.name,
                                status=StageStatus.PASS,
                                message=f"Rate limit triggered on attempt {i + 1} -> 429",
                                latency_ms=latency,
                            )
                        )
                        break

            if not hit_429:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.RATE_LIMIT_FAILURE,
                        message="Rate limit not triggered after 5 requests (limit=2/min)",
                    )
                )

            await auth_service.revoke_key(
                key_id, "live_validation", "Rate limit test complete"
            )

        except Exception as exc:
            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=StageStatus.ERROR,
                    defect=DefectType.RATE_LIMIT_FAILURE,
                    message=str(exc),
                    traceback_str=traceback.format_exc(),
                )
            )

        if not any(
            e.status == StageStatus.PASS and "429" in e.message for e in result.evidence
        ):
            result.status = StageStatus.FAIL
            result.defect = DefectType.RATE_LIMIT_FAILURE
        return result

    async def _request(self, client, token: str) -> tuple:
        start_t = time.time()
        try:
            resp = await client.get(
                "/health", headers={"Authorization": f"Bearer {token}"}
            )
            latency = (time.time() - start_t) * 1000
            return resp.status_code, {}, latency
        except Exception as exc:
            latency = (time.time() - start_t) * 1000
            return 0, {"error": str(exc)}, latency
