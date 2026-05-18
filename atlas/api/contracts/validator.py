from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from atlas.api.contracts.manifest import (
    RouteContract,
    ContractManifest,
    get_contract_manifest,
)


@dataclass
class ContractViolation:
    contract_key: str
    category: str
    severity: str
    message: str


@dataclass
class ContractValidationReport:
    passed: bool = False
    violations: list[ContractViolation] = field(default_factory=list)
    checked: int = 0
    manifest_count: int = 0
    app_route_count: int = 0

    @property
    def errors(self) -> list[ContractViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[ContractViolation]:
        return [v for v in self.violations if v.severity == "warning"]


AUTH_DEPS = {
    "verify_token",
    "verify_admin_token",
    "verify_trader_token",
    "verify_read_token",
    "verify_read_access",
    "verify_trader_access",
    "verify_admin_access",
}


def _extract_route_info(route: Any) -> Optional[dict]:
    if not hasattr(route, "methods") or not hasattr(route, "path"):
        return None

    methods = sorted(route.methods - {"HEAD", "OPTIONS"}) if route.methods else ["GET"]
    if not methods:
        return None

    dep_names: set[str] = set()
    try:
        dependant = getattr(route, "dependant", None)
        if dependant:
            deps = getattr(dependant, "dependencies", []) or []
            for d in deps:
                callable_fn = getattr(d, "call", None)
                if callable_fn:
                    dep_names.add(callable_fn.__name__)
                inner_deps = getattr(d, "dependencies", []) or []
                for inner in inner_deps:
                    inner_fn = getattr(inner, "call", None)
                    if inner_fn:
                        dep_names.add(inner_fn.__name__)
    except Exception:
        pass

    tags: list[str] = []
    try:
        raw_tags = getattr(route, "tags", []) or []
        tags = [
            t if isinstance(t, str) else (t.tag if hasattr(t, "tag") else str(t))
            for t in raw_tags
        ]
    except Exception:
        pass

    return {
        "path": route.path,
        "methods": methods,
        "dependencies": dep_names,
        "tags": tags,
    }


def _has_auth_dependency(dep_names: set[str]) -> bool:
    return bool(dep_names & AUTH_DEPS)


def validate_app_routes(
    app: Any,
    manifest: Optional[ContractManifest] = None,
) -> ContractValidationReport:
    """
    Validate all FastAPI routes against the contract manifest.

    Checks:
    1. Every manifest route exists in the app (missing = error)
    2. Every app route is documented in the manifest (missing = warning)
    3. Auth dependencies are present on auth-required routes (missing = error)
    4. Tags are consistent between manifest and app (mismatch = warning)
    """
    report = ContractValidationReport()
    manifest = manifest or get_contract_manifest()
    report.manifest_count = manifest.count

    app_routes: dict[str, dict] = {}
    for route in getattr(app, "routes", []):
        info = _extract_route_info(route)
        if info is None:
            continue
        for method in info["methods"]:
            key = f"{method.upper()} {info['path']}"
            app_routes[key] = info
    report.app_route_count = len(app_routes)

    for key, contract in manifest.routes.items():
        if key not in app_routes:
            report.violations.append(
                ContractViolation(
                    contract_key=key,
                    category="missing_route",
                    severity="error",
                    message=f"Route {key} is in manifest but NOT registered in the FastAPI app",
                )
            )
            continue

        route_info = app_routes[key]

        has_auth = _has_auth_dependency(route_info["dependencies"])
        if contract.auth_required and not has_auth:
            report.violations.append(
                ContractViolation(
                    contract_key=key,
                    category="auth_mismatch",
                    severity="error",
                    message=f"Route {key} requires auth per contract but has no auth dependency",
                )
            )

        if contract.tags and route_info["tags"]:
            manifest_tags_set = set(contract.tags)
            app_tags_set = set(route_info["tags"])
            if not manifest_tags_set.intersection(app_tags_set):
                report.violations.append(
                    ContractViolation(
                        contract_key=key,
                        category="tag_mismatch",
                        severity="warning",
                        message=f"Route {key} tags {route_info['tags']} don't match contract {contract.tags}",
                    )
                )

    for key in app_routes:
        if key not in manifest.routes:
            report.violations.append(
                ContractViolation(
                    contract_key=key,
                    category="missing_manifest",
                    severity="warning",
                    message=f"Route {key} exists in app but is NOT in contract manifest",
                )
            )

    report.checked = len(app_routes)
    report.passed = len(report.errors) == 0
    return report


def format_report(report: ContractValidationReport) -> str:
    lines = []
    lines.append(f"Contract Validation Report")
    lines.append(f"  Routes checked: {report.checked}")
    lines.append(f"  Manifest contracts: {report.manifest_count}")
    lines.append(f"  App routes: {report.app_route_count}")
    lines.append(f"  Status: {'PASS' if report.passed else 'FAIL'}")
    lines.append(f"  Errors: {len(report.errors)}  Warnings: {len(report.warnings)}")
    if report.violations:
        lines.append("")
        lines.append("  Violations:")
        for v in report.violations:
            marker = "ERROR" if v.severity == "error" else "WARN"
            lines.append(f"    [{marker}] [{v.category}] {v.message}")
    return "\n".join(lines)
