from __future__ import annotations

import traceback

from atlas.validation.base_stage import BaseStage
from atlas.validation.models import StageResult, StageStatus, DefectType, Evidence


class AuditStage(BaseStage):
    name = "08_audit_trail"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        db = ctx.db
        from sqlalchemy.sql import text as sql_text

        try:
            async with db.engine.connect() as conn:
                row = await conn.execute(
                    sql_text("SELECT COUNT(*) FROM api_request_audit")
                )
                audit_count = row.scalar() or 0
                row = await conn.execute(sql_text("SELECT COUNT(*) FROM audit_logs"))
                audit_log_count = row.scalar() or 0
                row = await conn.execute(sql_text("SELECT COUNT(*) FROM api_keys"))
                key_count = row.scalar() or 0
                row = await conn.execute(
                    sql_text("SELECT COUNT(*) FROM copy_execution_log")
                )
                copy_log_count = row.scalar() or 0

            if audit_count > 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"api_request_audit rows: {audit_count}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.AUDIT_FAILURE,
                        message="api_request_audit has 0 rows",
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.AUDIT_FAILURE

            if audit_log_count > 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"audit_logs rows: {audit_log_count}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        message=f"audit_logs rows: {audit_log_count}",
                    )
                )

            if key_count > 0:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"api_keys rows: {key_count}",
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.AUDIT_FAILURE,
                        message="api_keys has 0 rows",
                    )
                )

        except Exception as exc:
            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=StageStatus.ERROR,
                    defect=DefectType.AUDIT_FAILURE,
                    message=str(exc),
                    traceback_str=traceback.format_exc(),
                )
            )
            result.status = StageStatus.ERROR
            result.defect = DefectType.AUDIT_FAILURE

        return result
