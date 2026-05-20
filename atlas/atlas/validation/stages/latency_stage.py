from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence


class LatencyStage(BaseStage):
    name = "10_latency_metrics"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        all_results = getattr(ctx, "_all_results", {})
        latency_report = {n: round(s.latency_ms, 2) for n, s in all_results.items()}
        result.evidence.append(
            Evidence(
                stage=self.name,
                status=StageStatus.PASS,
                message="Latency metrics collected",
                detail=latency_report,
            )
        )
        for stage_name, lat in latency_report.items():
            if lat > 60000:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.LATENCY_FAILURE,
                        message=f"{stage_name} latency {lat:.0f}ms exceeds 60000ms threshold",
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.LATENCY_FAILURE
        return result
