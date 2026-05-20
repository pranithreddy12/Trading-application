from __future__ import annotations

import json
import time

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence


class HealthStage(BaseStage):
    name = "05_health_verification"

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
                    "/health", headers={"Authorization": f"Bearer {admin_key}"}
                )
                latency = (time.time() - start_t) * 1000
            except Exception as exc:
                result.status = StageStatus.FAIL
                result.defect = DefectType.HEALTH_FAILURE
                result.error = str(exc)
                return result

            if resp.status_code == 200:
                body = resp.json()
                checks = [
                    (
                        "status",
                        lambda b: b.get("status") in ("healthy", "ok", "degraded"),
                    ),
                    ("timestamp", lambda b: b.get("timestamp") is not None),
                    (
                        "latency_ms",
                        lambda b: isinstance(b.get("latency_ms"), (int, float)),
                    ),
                ]
                for check_name, check_fn in checks:
                    if check_fn(body):
                        result.evidence.append(
                            Evidence(
                                stage=self.name,
                                status=StageStatus.PASS,
                                message=f"health.{check_name} = {body.get(check_name)}",
                                latency_ms=latency,
                            )
                        )
                    else:
                        result.evidence.append(
                            Evidence(
                                stage=self.name,
                                status=StageStatus.FAIL,
                                defect=DefectType.HEALTH_FAILURE,
                                message=f"health.{check_name} missing or invalid",
                                latency_ms=latency,
                            )
                        )
                        result.status = StageStatus.FAIL
                        result.defect = DefectType.HEALTH_FAILURE

                components = body.get("components", {})
                if components:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"components: {json.dumps(components)}",
                            latency_ms=latency,
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.FAIL,
                            defect=DefectType.HEALTH_FAILURE,
                            message="health response missing components block",
                            latency_ms=latency,
                        )
                    )
                    result.status = StageStatus.FAIL
            else:
                result.status = StageStatus.FAIL
                result.defect = DefectType.HEALTH_FAILURE
                result.error = f"/health returned {resp.status_code}"
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.HEALTH_FAILURE,
                        message=f"HTTP {resp.status_code}",
                        latency_ms=latency,
                    )
                )

        return result
