from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .base_stage import BaseStage
from .models import (
    DefectType,
    Evidence,
    StageResult,
    StageStatus,
    ValidationOutput,
)
from .stages.schema_stage import SchemaStage
from .stages.key_gen_stage import KeyGenStage
from .stages.route_stage import RouteStage
from .stages.rate_limit_stage import RateLimitStage
from .stages.health_stage import HealthStage
from .stages.copy_stage import CopyStage
from .stages.security_matrix_stage import SecurityMatrixStage
from .stages.audit_stage import AuditStage
from .stages.restart_stage import RestartStage
from .stages.latency_stage import LatencyStage
from .stages.mutator_check import MutatorCheckStage
from .stages.contract_stage import ContractStage
from .stages.event_lineage_stage import EventLineageStage


class ValidationContext:
    def __init__(self):
        self.db = None
        self.auth_service = None
        self.http_client = None
        self.generated_keys: dict[str, dict] = {}
        self.security_matrix: dict[str, dict[str, str]] = {}
        self.settings = None
        self.api_base: str = "http://localhost:8000"


class ValidationHarness:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("validation_output")
        self.stages: list[BaseStage] = []
        self.ctx = ValidationContext()
        self.trace_id: str = ""
        self._register_default_stages()

    def _register_default_stages(self):
        self.stages = [
            SchemaStage(),
            KeyGenStage(),
            RouteStage(),
            RateLimitStage(),
            HealthStage(),
            CopyStage(),
            SecurityMatrixStage(),
            AuditStage(),
            RestartStage(),
            MutatorCheckStage(),
            ContractStage(),
            EventLineageStage(),
            LatencyStage(),
        ]

    def add_stage(self, stage: BaseStage):
        self.stages.append(stage)

    def set_api_base(self, url: str):
        self.ctx.api_base = url

    async def initialize(self):
        sys.path.insert(0, str(Path.cwd()))
        from atlas.config.settings import settings
        from atlas.data.storage.timescale_client import TimescaleClient
        from atlas.api.services.auth_service import AuthService

        self.ctx.settings = settings
        self.ctx.db = TimescaleClient(settings.database_url)
        await self.ctx.db.connect()
        self.ctx.auth_service = AuthService(self.ctx.db)
        logger.info("ValidationHarness initialized (DB connected)")

    async def run_all(self) -> ValidationOutput:
        self.trace_id = uuid.uuid4().hex[:12]
        output = ValidationOutput(
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=os.environ.get("ATLAS_ENV", "development"),
            overall_status=StageStatus.PASS,
            trace_id=self.trace_id,
        )
        logger.info(f"ValidationHarness [{self.trace_id}] — {len(self.stages)} stages")

        await self._pre_cleanup()

        all_results = {}
        for stage in self.stages:
            logger.info(f"  Stage: {stage.name}")
            result = await stage.execute(self.ctx)
            output.stages[stage.name] = result
            all_results[stage.name] = result
            self._log_stage_result(result)

        self.ctx._all_results = all_results
        # Re-run latency stage with access to all results
        if "10_latency_metrics" in output.stages:
            latency_result = await LatencyStage().execute(self.ctx)
            output.stages["10_latency_metrics"] = latency_result
            all_results["10_latency_metrics"] = latency_result

        output.security_matrix = self.ctx.security_matrix
        await self._post_cleanup()
        self._build_summary(output)
        output.write(self.output_dir / "validation_output.json")
        self._print_summary(output)
        return output

    async def run_stage(self, name: str) -> Optional[StageResult]:
        for stage in self.stages:
            if stage.name == name:
                return await stage.execute(self.ctx)
        logger.warning(f"Stage '{name}' not found")
        return None

    async def _pre_cleanup(self):
        logger.info("  Pre-cleanup: revoking stale keys")
        try:
            from sqlalchemy.sql import text as sql_text

            async with self.ctx.db.engine.begin() as conn:
                await conn.execute(
                    sql_text(
                        "UPDATE api_keys SET revoked_at = NOW(), revoke_reason = 'pre_validation_cleanup' "
                        "WHERE revoked_at IS NULL"
                    )
                )
            logger.info("    All active api_keys revoked")
        except Exception as exc:
            logger.warning(f"    Pre-cleanup warning: {exc}")

    async def _post_cleanup(self):
        logger.info("  Post-cleanup: revoking test keys")
        try:
            from sqlalchemy.sql import text as sql_text

            async with self.ctx.db.engine.begin() as conn:
                await conn.execute(
                    sql_text(
                        "UPDATE api_keys SET revoked_at = NOW(), revoke_reason = 'live_validation_cleanup' "
                        "WHERE description LIKE 'Live validation%' AND revoked_at IS NULL"
                    )
                )
            logger.info("    Test keys revoked")
        except Exception as exc:
            logger.warning(f"    Post-cleanup warning: {exc}")

    def _log_stage_result(self, result: StageResult):
        logger.info(
            f"    [{result.status.value}] {result.stage_name} ({result.latency_ms:.0f}ms)"
        )
        if result.error:
            logger.error(f"      Error: {result.error}")
        if result.defect:
            logger.warning(f"      Defect: {result.defect.value}")

    def _build_summary(self, output: ValidationOutput):
        all_results = output.stages
        total = len(all_results)
        passed = sum(1 for s in all_results.values() if s.status == StageStatus.PASS)
        failed = sum(1 for s in all_results.values() if s.status == StageStatus.FAIL)
        errors = sum(1 for s in all_results.values() if s.status == StageStatus.ERROR)
        skipped = sum(
            1 for s in all_results.values() if s.status == StageStatus.SKIPPED
        )
        defect_counts: dict[str, int] = {}
        for s in all_results.values():
            if s.defect:
                defect_counts[s.defect.value] = defect_counts.get(s.defect.value, 0) + 1
        output.overall_status = (
            StageStatus.PASS if failed == 0 and errors == 0 else StageStatus.FAIL
        )
        output.summary = {
            "total_stages": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "defects": defect_counts,
            "schema_errors": defect_counts.get("schema_failure", 0),
            "auth_errors": defect_counts.get("auth_failure", 0)
            + defect_counts.get("permission_failure", 0),
            "rate_limit_429_confirmed": any(
                "429" in e.message for s in all_results.values() for e in s.evidence
            ),
            "audit_rows_gt_zero": any(
                e.status == StageStatus.PASS and "rows" in e.message
                for s in all_results.values()
                for e in s.evidence
            ),
            "key_generation_pass": output.stages.get(
                "02_key_generation", StageResult("", StageStatus.FAIL)
            ).status
            == StageStatus.PASS,
        }
        output.latency_report = {
            n: round(s.latency_ms, 2) for n, s in all_results.items()
        }

    def _print_summary(self, output: ValidationOutput):
        s = output.summary
        logger.info("=" * 70)
        logger.info(f"  VALIDATION COMPLETE [{self.trace_id}]")
        logger.info(f"  Overall: {output.overall_status.value}")
        logger.info(
            f"  Stages: {s['passed']}/{s['total_stages']} passed, {s['failed']} failed, {s['errors']} errors, {s['skipped']} skipped"
        )
        if s["defects"]:
            logger.info(f"  Defects: {json.dumps(s['defects'])}")
        logger.info("=" * 70)
