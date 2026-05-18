from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class RouteContract:
    path: str
    method: str
    auth_required: bool = True
    allowed_roles: list[str] = field(
        default_factory=lambda: ["admin", "trader", "read_only", "follower", "monitor"]
    )
    rate_limit_tier: str = "read_only"
    audit_required: bool = True
    expected_status_codes: list[int] = field(
        default_factory=lambda: [200, 401, 403, 429]
    )
    tags: list[str] = field(default_factory=list)
    description: str = ""
    response_fields: list[str] = field(default_factory=list)
    scope_required: Optional[str] = None


MANIFEST: dict[str, RouteContract] = {
    "GET /health": RouteContract(
        path="/health",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "follower", "monitor"],
        rate_limit_tier="read_only",
        tags=["Health"],
        description="System health status with DB ping and component checks",
        response_fields=["status", "version", "latency_ms"],
    ),
    "GET /copy/logs": RouteContract(
        path="/copy/logs",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "follower"],
        rate_limit_tier="read_only",
        tags=["Copy Trading"],
        description="Copy execution audit trail with filtering",
        response_fields=["logs", "count", "latency_ms"],
    ),
    "GET /leaders": RouteContract(
        path="/leaders",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "follower"],
        rate_limit_tier="read_only",
        tags=["Leaders"],
        description="List active leader accounts",
        response_fields=["leaders", "latency_ms"],
    ),
    "GET /followers": RouteContract(
        path="/followers",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "follower"],
        rate_limit_tier="read_only",
        tags=["Followers"],
        description="List follower subscriptions with allocation ratios",
        response_fields=["followers", "count", "latency_ms"],
    ),
    "GET /portfolio": RouteContract(
        path="/portfolio",
        method="GET",
        allowed_roles=["admin", "trader", "read_only"],
        rate_limit_tier="read_only",
        tags=["Portfolio"],
        description="Portfolio summary (placeholder in Day 4)",
        response_fields=["status", "leaders", "followers", "latency_ms"],
    ),
    "GET /positions": RouteContract(
        path="/positions",
        method="GET",
        allowed_roles=["admin", "trader", "read_only"],
        rate_limit_tier="read_only",
        tags=["Portfolio"],
        description="Open positions snapshot",
        response_fields=["count", "positions", "latency_ms"],
    ),
    "GET /risk": RouteContract(
        path="/risk",
        method="GET",
        allowed_roles=["admin", "trader", "read_only"],
        rate_limit_tier="read_only",
        tags=["Risk"],
        description="Portfolio risk metrics",
        response_fields=["risk", "latency_ms"],
    ),
    "GET /strategies": RouteContract(
        path="/strategies",
        method="GET",
        allowed_roles=["admin", "trader", "read_only"],
        rate_limit_tier="read_only",
        tags=["Strategies"],
        description="List validated strategies with metrics",
        response_fields=["count", "strategies", "latency_ms"],
    ),
    "GET /status": RouteContract(
        path="/status",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "monitor"],
        rate_limit_tier="read_only",
        tags=["Status"],
        description="Comprehensive system status with copy trader metrics",
        response_fields=["timestamp", "copy_trader", "accounts", "latency_ms"],
    ),
    "GET /copy/status": RouteContract(
        path="/copy/status",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "follower"],
        rate_limit_tier="read_only",
        tags=["Copy Trading"],
        description="Copy trading system status",
        response_fields=["copy_status", "latency_ms"],
    ),
    "GET /docs": RouteContract(
        path="/docs",
        method="GET",
        auth_required=False,
        allowed_roles=[],
        tags=["Documentation"],
        description="Swagger UI documentation",
    ),
    "GET /redoc": RouteContract(
        path="/redoc",
        method="GET",
        auth_required=False,
        allowed_roles=[],
        tags=["Documentation"],
        description="ReDoc documentation",
    ),
    "GET /openapi.json": RouteContract(
        path="/openapi.json",
        method="GET",
        auth_required=False,
        allowed_roles=[],
        tags=["Documentation"],
        description="OpenAPI schema",
    ),
    "GET /docs/oauth2-redirect": RouteContract(
        path="/docs/oauth2-redirect",
        method="GET",
        auth_required=False,
        allowed_roles=[],
        tags=["Documentation"],
        description="OAuth2 redirect for Swagger UI",
    ),
    "GET /dashboard/api/execution/logs": RouteContract(
        path="/dashboard/api/execution/logs",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "monitor"],
        rate_limit_tier="read_only",
        tags=["Execution"],
        description="Execution logs for dashboard",
        response_fields=["logs"],
    ),
    "GET /dashboard/api/execution/dead-letters": RouteContract(
        path="/dashboard/api/execution/dead-letters",
        method="GET",
        allowed_roles=["admin", "trader", "read_only", "monitor"],
        rate_limit_tier="read_only",
        tags=["Execution"],
        description="Dead letters for dashboard",
        response_fields=["dead_letters"],
    ),
}


class ContractManifest:
    def __init__(self, contracts: dict[str, RouteContract] | None = None):
        self._contracts: dict[str, RouteContract] = contracts or dict(MANIFEST)

    def get(self, method: str, path: str) -> Optional[RouteContract]:
        key = f"{method.upper()} {path}"
        return self._contracts.get(key)

    def get_by_key(self, key: str) -> Optional[RouteContract]:
        return self._contracts.get(key)

    @property
    def routes(self) -> dict[str, RouteContract]:
        return dict(self._contracts)

    @property
    def count(self) -> int:
        return len(self._contracts)

    def get_roles_for(self, method: str, path: str) -> list[str]:
        c = self.get(method, path)
        return list(c.allowed_roles) if c else []

    def auth_required_for(self, method: str, path: str) -> bool:
        c = self.get(method, path)
        return c.auth_required if c else True

    def add_contract(self, contract: RouteContract) -> None:
        key = f"{contract.method.upper()} {contract.path}"
        self._contracts[key] = contract


def get_contract_manifest() -> ContractManifest:
    return ContractManifest()
