from __future__ import annotations

import traceback

from atlas.validation.base_stage import BaseStage
from atlas.validation.models import StageResult, StageStatus, DefectType, Evidence

ROLES_TO_CREATE = [
    ("admin_user", "admin"),
    ("trader_user", "trader"),
    ("readonly_user", "read_only"),
    ("follower_user", "follower"),
    ("monitor_user", "monitor"),
]


class KeyGenStage(BaseStage):
    name = "02_key_generation"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        auth_service = ctx.auth_service
        from atlas.api.services.auth_service import APIRole

        generated_keys = {}
        for user_id, role_str in ROLES_TO_CREATE:
            role_enum = APIRole(role_str)
            try:
                raw_key, key_id = await auth_service.generate_api_key(
                    user_id=user_id,
                    role=role_enum,
                    created_by="live_validation",
                    description=f"Live validation key for {role_str}",
                    expires_in_days=1,
                )
                generated_keys[role_str] = {"raw_key": raw_key, "key_id": key_id}
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.PASS,
                        message=f"Generated {role_str} key: {str(key_id)[:8]}...",
                    )
                )
            except Exception as exc:
                result.evidence.append(
                    Evidence(
                        stage=self.name,
                        status=StageStatus.FAIL,
                        defect=DefectType.AUTH_FAILURE,
                        message=f"Failed to generate {role_str} key: {exc}",
                        traceback_str=traceback.format_exc(),
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.AUTH_FAILURE

        result.evidence.append(
            Evidence(
                stage=self.name,
                status=StageStatus.PASS if generated_keys else StageStatus.FAIL,
                message="Generated keys available for downstream stages",
                detail={
                    role: k["key_id"][:8] + "..." for role, k in generated_keys.items()
                },
            )
        )
        ctx.generated_keys = generated_keys
        return result
