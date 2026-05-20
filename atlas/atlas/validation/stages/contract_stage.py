from __future__ import annotations

import importlib
import sys

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence
from atlas.api.contracts.manifest import get_contract_manifest
from atlas.api.contracts.validator import validate_app_routes, format_report


class ContractStage(BaseStage):
    name = "12_contract_governance"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)

        # Import the FastAPI app to introspect its routes
        try:
            from atlas.api.day4_api import app as day4_app
        except Exception as exc:
            result.status = StageStatus.FAIL
            result.defect = DefectType.CONTRACT_FAILURE
            result.error = f"Cannot import FastAPI app: {exc}"
            return result

        # Run contract validation
        manifest = get_contract_manifest()
        report = validate_app_routes(day4_app, manifest)

        # Record evidence for each check
        result.evidence.append(
            Evidence(
                stage=self.name,
                status=StageStatus.PASS if report.passed else StageStatus.FAIL,
                message=f"Contract validation: {report.checked} routes checked, {len(report.errors)} errors, {len(report.warnings)} warnings",
                detail={
                    "routes_checked": report.checked,
                    "manifest_contracts": report.manifest_count,
                    "app_routes": report.app_route_count,
                    "errors": len(report.errors),
                    "warnings": len(report.warnings),
                },
            )
        )

        # Add evidence per route
        for route_key in manifest.routes:
            contract = manifest.get_by_key(route_key)
            if contract:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"Contract OK: {route_key} (roles={contract.allowed_roles}, tags={contract.tags})",
                    )
                )

        # Add evidence for violations
        for v in report.violations:
            status = StageStatus.FAIL if v.severity == "error" else StageStatus.PASS
            result.evidence.append(
                Evidence(
                    stage=self.name,
                    status=status,
                    defect=DefectType.CONTRACT_FAILURE
                    if v.severity == "error"
                    else None,
                    message=f"[{v.category}] {v.message}",
                    detail={"severity": v.severity, "contract_key": v.contract_key},
                )
            )

        if not report.passed:
            result.status = StageStatus.FAIL
            result.defect = DefectType.CONTRACT_FAILURE
            error_count = len(report.errors)
            result.error = f"Contract governance: {error_count} error(s), {len(report.warnings)} warning(s)"

        return result
