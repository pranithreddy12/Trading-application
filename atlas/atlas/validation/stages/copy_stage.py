from __future__ import annotations

import time

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence

REQUIRED_FIELDS = [
    "timestamp",
    "running_state",
    "active_leaders",
    "active_followers",
    "filled_orders",
]


class CopyStage(BaseStage):
    name = "06_copy_status"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        import httpx

        admin_key = ctx.generated_keys.get("admin", {}).get("raw_key")
        if not admin_key:
            result.status = StageStatus.SKIPPED
            result.error = "No admin key"
            return result

        async with httpx.AsyncClient(base_url=ctx.api_base, timeout=10.0) as client:
            start_t = time.time()
            try:
                resp = await client.get(
                    "/copy/status", headers={"Authorization": f"Bearer {admin_key}"}
                )
                latency = (time.time() - start_t) * 1000
            except Exception as exc:
                result.status = StageStatus.FAIL
                result.defect = DefectType.HEALTH_FAILURE
                result.error = str(exc)
                return result

            if resp.status_code == 200:
                body = resp.json()
                for field in REQUIRED_FIELDS:
                    if field in body:
                        result.evidence.append(
                            Evidence(
                                stage=self.name,
                                status=StageStatus.PASS,
                                message=f"copy_status.{field} = {body.get(field)}",
                                latency_ms=latency,
                            )
                        )
                    else:
                        result.evidence.append(
                            Evidence(
                                stage=self.name,
                                status=StageStatus.FAIL,
                                defect=DefectType.SERIALIZATION_FAILURE,
                                message=f"copy_status missing field: {field}",
                                latency_ms=latency,
                            )
                        )
                        result.status = StageStatus.FAIL
                        result.defect = DefectType.SERIALIZATION_FAILURE
            else:
                result.status = StageStatus.FAIL
                result.defect = DefectType.HEALTH_FAILURE
                result.error = f"/copy/status returned {resp.status_code}"
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        message=f"HTTP {resp.status_code}",
                        latency_ms=latency,
                    )
                )

        return result
