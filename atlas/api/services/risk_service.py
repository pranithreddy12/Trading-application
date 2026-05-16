from __future__ import annotations

from typing import Any


class RiskService:
    """Risk governance surface for copy execution and API visibility."""

    async def check_copy_allowed(self, follower: dict[str, Any], qty: float) -> tuple[bool, str | None]:
        max_position_pct = float(follower.get("max_position_pct") or 0.0)
        if max_position_pct <= 0:
            return False, "invalid_max_position_pct"
        if qty <= 0:
            return False, "invalid_quantity"
        return True, None

    async def get_risk_snapshot(self) -> dict[str, Any]:
        return {
            "status": "placeholder",
            "message": "RiskService active; advanced risk metrics rollout in next phase",
            "portfolio_var": None,
            "max_drawdown": None,
            "leverage_ratio": None,
            "kill_switch": "not_triggered",
        }
