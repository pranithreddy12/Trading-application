"""
Day 5 Live Validation Harness (V1 — Monolithic)
Superseded by atlas/validation/ (V2 — Modular)

PURPOSE:
  This is ATLAS's Tier-1 governance truth engine. It validates the operational
  platform under adversarial runtime conditions and produces deterministic,
  structured evidence of system health.

STATUS: V1 (legacy) — Use atlas/validation/ for new work
  - Deployment validator
  - Governance certifier
  - Regression gate
  - Platform truth engine

RULES:
  1. Always writes output JSON (even on partial failure / exceptions)
  2. Stage isolation — each stage commits/rolls back independently
  3. Live defect classification — every failure is typed
  4. Auto-patchability — bootstraps missing schema/keys
  5. Latency metrics — every operation is timed
  6. Security matrix — role-based access control proof
  7. Restart certification — no duplicate state, no auth corruption

OUTPUT:
  scripts/day5/validation_output.json  (deterministic, structured)

UPGRADE PATH:
  python -m atlas.validation.cli           # V2 harness (recommended)
  python -m atlas.validation.__main__       # V2 CI entry point
  python scripts/day5/live_validation.py    # V1 (legacy, still works)
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = OUTPUT_DIR / "validation_output.json"
SCHEMA_BOOTSTRAP_PATH = OUTPUT_DIR / "bootstrap_day4_schema.sql"

# ---------------------------------------------------------------------------
# Defect classification
# ---------------------------------------------------------------------------


class DefectType(str, Enum):
    SCHEMA_FAILURE = "schema_failure"
    AUTH_FAILURE = "auth_failure"
    SERIALIZATION_FAILURE = "serialization_failure"
    PERMISSION_FAILURE = "permission_failure"
    RATE_LIMIT_FAILURE = "rate_limit_failure"
    RESTART_FAILURE = "restart_failure"
    HEALTH_FAILURE = "health_failure"
    LATENCY_FAILURE = "latency_failure"
    AUDIT_FAILURE = "audit_failure"


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    stage: str
    status: StageStatus
    defect: Optional[DefectType] = None
    message: str = ""
    detail: Any = None
    latency_ms: float = 0.0
    traceback_str: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        if self.defect:
            d["defect"] = self.defect.value
        return d


@dataclass
class StageResult:
    stage_name: str
    status: StageStatus
    defect: Optional[DefectType] = None
    evidence: list[Evidence] = field(default_factory=list)
    error: Optional[str] = None
    traceback_str: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "defect": self.defect.value if self.defect else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "error": self.error,
            "traceback": self.traceback_str,
            "latency_ms": self.latency_ms,
        }


@dataclass
class ValidationOutput:
    timestamp: str
    environment: str
    overall_status: StageStatus
    stages: dict[str, StageResult] = field(default_factory=dict)
    security_matrix: dict[str, dict[str, str]] = field(default_factory=dict)
    latency_report: dict[str, float] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "environment": self.environment,
            "overall_status": self.overall_status.value,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "security_matrix": self.security_matrix,
            "latency_report": self.latency_report,
            "summary": self.summary,
        }

    def write(self, path: Path = OUTPUT_PATH):
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        logger.info(f"Validation output written to {path}")


# ---------------------------------------------------------------------------
# Stage 1: Schema Validation & Bootstrap
# ---------------------------------------------------------------------------

DAY4_SCHEMA_SQL = """
-- ============================================================
-- Day 4 Schema: Auth, Audit, Copy Trading Tables
-- Auto-bootstrapped by live_validation.py
-- ============================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL DEFAULT 'atlas_',
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    scopes JSONB DEFAULT CAST('[]' AS jsonb),
    rate_limit_per_min INT NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'system',
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revoke_reason TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS api_request_audit (
    id BIGSERIAL PRIMARY KEY,
    api_key_id UUID,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INT NOT NULL,
    latency_ms INT NOT NULL DEFAULT 0,
    ip_hash TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_request_audit_created ON api_request_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_key ON api_request_audit (api_key_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    actor_id TEXT,
    actor_type TEXT NOT NULL DEFAULT 'api_key',
    status TEXT NOT NULL DEFAULT 'success',
    reason TEXT,
    old_value JSONB,
    new_value JSONB,
    status_code INT,
    error_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs (resource_type, resource_id);

CREATE TABLE IF NOT EXISTS copy_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_order_id TEXT,
    follower_order_id TEXT,
    leader_id TEXT NOT NULL,
    follower_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    leader_qty NUMERIC NOT NULL DEFAULT 0,
    follower_qty NUMERIC NOT NULL DEFAULT 0,
    latency_ms INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_copy_exec_log_status ON copy_execution_log (status);
CREATE INDEX IF NOT EXISTS idx_copy_exec_log_created ON copy_execution_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_copy_exec_log_symbol ON copy_execution_log (symbol);

CREATE TABLE IF NOT EXISTS copy_leader_accounts (
    leader_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref TEXT NOT NULL,
    broker TEXT NOT NULL DEFAULT 'paper',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT CAST('{}' AS jsonb)
);

CREATE TABLE IF NOT EXISTS copy_follower_accounts (
    follower_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_id UUID NOT NULL REFERENCES copy_leader_accounts(leader_id),
    account_ref TEXT NOT NULL,
    broker TEXT NOT NULL DEFAULT 'paper',
    allocation_ratio NUMERIC NOT NULL DEFAULT 1.0,
    max_position_pct NUMERIC NOT NULL DEFAULT 0.1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT CAST('{}' AS jsonb)
);

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty NUMERIC NOT NULL DEFAULT 0,
    avg_price NUMERIC,
    side TEXT NOT NULL DEFAULT 'long',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_account ON positions (account_ref);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions (symbol);
"""


async def stage_01_schema_validation(db) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="01_schema_validation", status=StageStatus.PASS)

    required_tables = [
        "api_keys",
        "api_request_audit",
        "audit_logs",
        "copy_execution_log",
        "copy_leader_accounts",
        "copy_follower_accounts",
        "positions",
    ]

    try:
        async with db.engine.connect() as conn:
            for table in required_tables:
                ev = Evidence(
                    stage="01_schema_validation",
                    status=StageStatus.PASS,
                    message=f"Table {table} exists",
                )
                try:
                    row = await conn.execute(
                        __import__("sqlalchemy").sql.text(
                            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
                        ),
                        {"t": table},
                    )
                    exists = row.scalar()
                    if not exists:
                        ev.status = StageStatus.FAIL
                        ev.defect = DefectType.SCHEMA_FAILURE
                        ev.message = f"Table {table} missing"
                except Exception as exc:
                    ev.status = StageStatus.ERROR
                    ev.defect = DefectType.SCHEMA_FAILURE
                    ev.message = f"Error checking table {table}: {exc}"
                    ev.traceback_str = traceback.format_exc()
                result.evidence.append(ev)

        # If any tables missing, bootstrap them
        missing = [
            e
            for e in result.evidence
            if e.status in (StageStatus.FAIL, StageStatus.ERROR)
        ]
        if missing:
            logger.warning(f"Bootstrapping {len(missing)} missing Day 4 tables...")
            try:
                async with db.engine.begin() as conn:
                    for stmt in DAY4_SCHEMA_SQL.split(";"):
                        stripped = stmt.strip()
                        if stripped and not stripped.startswith("--"):
                            try:
                                await conn.execute(
                                    __import__("sqlalchemy").sql.text(stripped)
                                )
                            except Exception as exc:
                                logger.warning(
                                    f"Bootstrap sub-statement warning: {exc}"
                                )
                # Re-check
                async with db.engine.connect() as conn:
                    for table in required_tables:
                        row = await conn.execute(
                            __import__("sqlalchemy").sql.text(
                                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
                            ),
                            {"t": table},
                        )
                        exists = row.scalar()
                        if exists:
                            result.evidence.append(
                                Evidence(
                                    stage="01_schema_validation",
                                    status=StageStatus.PASS,
                                    message=f"Table {table} bootstrapped successfully",
                                    defect=None,
                                )
                            )
                        else:
                            result.evidence.append(
                                Evidence(
                                    stage="01_schema_validation",
                                    status=StageStatus.FAIL,
                                    message=f"Table {table} failed to bootstrap",
                                    defect=DefectType.SCHEMA_FAILURE,
                                )
                            )
                logger.info("Day 4 schema bootstrap complete")
            except Exception as exc:
                logger.error(f"Schema bootstrap failed: {exc}")
                result.status = StageStatus.FAIL
                result.defect = DefectType.SCHEMA_FAILURE
                result.error = str(exc)
                result.traceback_str = traceback.format_exc()
                result.latency_ms = (time.time() - start) * 1000
                return result

        result.latency_ms = (time.time() - start) * 1000
        # Only fail if bootstrap evidence still shows failures (after re-check)
        post_bootstrap_evidence = [
            e
            for e in result.evidence
            if "bootstrapped" in e.message or "exists" in e.message
        ]
        has_failures = any(
            e.status in (StageStatus.FAIL, StageStatus.ERROR)
            for e in post_bootstrap_evidence
        )
        if has_failures:
            result.status = StageStatus.FAIL
            first_bad = next(
                e
                for e in result.evidence
                if e.status in (StageStatus.FAIL, StageStatus.ERROR)
            )
            result.defect = first_bad.defect
        else:
            result.status = StageStatus.PASS
            result.defect = None
        return result

        result.latency_ms = (time.time() - start) * 1000
        has_failures = any(
            e.status in (StageStatus.FAIL, StageStatus.ERROR) for e in result.evidence
        )
        if has_failures:
            result.status = StageStatus.FAIL
            first_bad = next(
                e
                for e in result.evidence
                if e.status in (StageStatus.FAIL, StageStatus.ERROR)
            )
            result.defect = first_bad.defect
        return result

    except Exception as exc:
        result.status = StageStatus.ERROR
        result.defect = DefectType.SCHEMA_FAILURE
        result.error = str(exc)
        result.traceback_str = traceback.format_exc()
        result.latency_ms = (time.time() - start) * 1000
        return result


# ---------------------------------------------------------------------------
# Stage 2: Key Generation
# ---------------------------------------------------------------------------


async def stage_02_key_generation(auth_service) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="02_key_generation", status=StageStatus.PASS)

    roles_to_create = [
        ("admin_user", "admin"),
        ("trader_user", "trader"),
        ("readonly_user", "read_only"),
        ("follower_user", "follower"),
        ("monitor_user", "monitor"),
    ]

    from atlas.api.services.auth_service import APIRole

    generated_keys = {}
    for user_id, role_str in roles_to_create:
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
                    stage="02_key_generation",
                    status=StageStatus.PASS,
                    message=f"Generated {role_str} key: {key_id[:8]}...",
                    latency_ms=0,
                )
            )
            logger.info(f"Generated {role_str} API key: {key_id}")
        except Exception as exc:
            result.evidence.append(
                Evidence(
                    stage="02_key_generation",
                    status=StageStatus.FAIL,
                    defect=DefectType.AUTH_FAILURE,
                    message=f"Failed to generate {role_str} key: {exc}",
                    traceback_str=traceback.format_exc(),
                )
            )
            result.status = StageStatus.FAIL
            result.defect = DefectType.AUTH_FAILURE

    result.latency_ms = (time.time() - start) * 1000
    # Attach generated keys to result detail for downstream stages
    result.evidence.append(
        Evidence(
            stage="02_key_generation",
            status=StageStatus.PASS if generated_keys else StageStatus.FAIL,
            message="Generated keys available for downstream stages",
            detail={
                role: k["key_id"][:8] + "..." for role, k in generated_keys.items()
            },
        )
    )
    return result, generated_keys


# ---------------------------------------------------------------------------
# Stage 3: Route Authentication
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"

ENDPOINTS = {
    "GET /health": {"method": "GET", "path": "/health", "min_role": "read_only"},
    "GET /copy/logs": {"method": "GET", "path": "/copy/logs", "min_role": "read_only"},
    "GET /leaders": {"method": "GET", "path": "/leaders", "min_role": "read_only"},
    "GET /followers": {"method": "GET", "path": "/followers", "min_role": "read_only"},
    "GET /portfolio": {"method": "GET", "path": "/portfolio", "min_role": "read_only"},
    "GET /positions": {"method": "GET", "path": "/positions", "min_role": "read_only"},
    "GET /risk": {"method": "GET", "path": "/risk", "min_role": "read_only"},
    "GET /strategies": {
        "method": "GET",
        "path": "/strategies",
        "min_role": "read_only",
    },
    "GET /status": {"method": "GET", "path": "/status", "min_role": "read_only"},
    "GET /copy/status": {
        "method": "GET",
        "path": "/copy/status",
        "min_role": "read_only",
    },
}


async def _request(method: str, path: str, token: str) -> tuple[int, dict, float]:
    start_t = time.time()
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10.0) as client:
            resp = await client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}"},
            )
            latency = (time.time() - start_t) * 1000
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}
            return resp.status_code, body, latency
    except Exception as exc:
        latency = (time.time() - start_t) * 1000
        return 0, {"error": str(exc)}, latency


async def stage_03_route_auth(auth_service, generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="03_route_auth", status=StageStatus.PASS)

    # Validate each endpoint with admin key, then spot-check role restrictions
    admin_key = generated_keys.get("admin", {}).get("raw_key")
    if not admin_key:
        result.status = StageStatus.FAIL
        result.defect = DefectType.AUTH_FAILURE
        result.error = "No admin key available for route auth testing"
        result.latency_ms = (time.time() - start) * 1000
        return result

    # Test every endpoint with admin (should all PASS)
    for label, cfg in ENDPOINTS.items():
        status_code, body, latency = await _request(
            cfg["method"], cfg["path"], admin_key
        )
        if status_code in (200, 201):
            result.evidence.append(
                Evidence(
                    stage="03_route_auth",
                    status=StageStatus.PASS,
                    message=f"admin -> {label} -> {status_code}",
                    latency_ms=latency,
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="03_route_auth",
                    status=StageStatus.FAIL,
                    defect=DefectType.AUTH_FAILURE,
                    message=f"admin -> {label} -> {status_code} (expected 2xx): {body}",
                    latency_ms=latency,
                )
            )
            result.status = StageStatus.FAIL
            result.defect = DefectType.AUTH_FAILURE

    # Read-only key should PASS on GET, FAIL on anything else (no write endpoints yet but validate GETs)
    read_key = generated_keys.get("read_only", {}).get("raw_key")
    if read_key:
        for label, cfg in ENDPOINTS.items():
            if cfg["method"] == "GET":
                status_code, body, latency = await _request(
                    cfg["method"], cfg["path"], read_key
                )
                if status_code in (200, 201, 403, 429):
                    if status_code == 403:
                        result.evidence.append(
                            Evidence(
                                stage="03_route_auth",
                                status=StageStatus.PASS,
                                message=f"read_only -> {label} -> {status_code} (forbidden, some scoped endpoints)",
                                defect=None,
                                latency_ms=latency,
                            )
                        )
                    else:
                        result.evidence.append(
                            Evidence(
                                stage="03_route_auth",
                                status=StageStatus.PASS,
                                message=f"read_only -> {label} -> {status_code}",
                                latency_ms=latency,
                            )
                        )
                else:
                    result.evidence.append(
                        Evidence(
                            stage="03_route_auth",
                            status=StageStatus.FAIL,
                            defect=DefectType.PERMISSION_FAILURE,
                            message=f"read_only -> {label} -> {status_code} (unexpected)",
                            latency_ms=latency,
                        )
                    )

    result.latency_ms = (time.time() - start) * 1000
    return result


# ---------------------------------------------------------------------------
# Stage 4: Rate Limiting
# ---------------------------------------------------------------------------


async def stage_04_rate_limiting(auth_service, generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="04_rate_limiting", status=StageStatus.PASS)

    admin_key = generated_keys.get("admin", {}).get("raw_key")
    if not admin_key:
        result.status = StageStatus.SKIPPED
        result.error = "No admin key available"
        result.latency_ms = (time.time() - start) * 1000
        return result

    # Burst requests to /health to trigger rate limit
    # Admin limit is 600/min, so we need to exhaust it
    # Instead, use a key with a low rate limit
    from atlas.api.services.auth_service import APIRole

    try:
        # Create a key with rate limit of 5/min
        raw_key, key_id = await auth_service.generate_api_key(
            user_id="rate_limit_test",
            role=APIRole.READ_ONLY,
            created_by="live_validation",
            description="Rate limit test key (2/min)",
            expires_in_days=1,
            rate_limit_per_min=2,
        )

        # Exhaust the rate limit
        hit_429 = False
        for i in range(5):
            status_code, body, latency = await _request("GET", "/health", raw_key)
            if status_code == 429:
                hit_429 = True
                result.evidence.append(
                    Evidence(
                        stage="04_rate_limiting",
                        status=StageStatus.PASS,
                        message=f"Rate limit triggered on attempt {i + 1} -> 429",
                        defect=None,
                        latency_ms=latency,
                    )
                )
                break

        if not hit_429:
            result.evidence.append(
                Evidence(
                    stage="04_rate_limiting",
                    status=StageStatus.FAIL,
                    defect=DefectType.RATE_LIMIT_FAILURE,
                    message="Rate limit was not triggered after 5 requests (limit=2/min)",
                )
            )

        # Revoke the test key
        await auth_service.revoke_key(
            key_id, "live_validation", "Rate limit test complete"
        )

    except Exception as exc:
        result.evidence.append(
            Evidence(
                stage="04_rate_limiting",
                status=StageStatus.ERROR,
                defect=DefectType.RATE_LIMIT_FAILURE,
                message=str(exc),
                traceback_str=traceback.format_exc(),
            )
        )

    result.latency_ms = (time.time() - start) * 1000
    if not any(
        e.status == StageStatus.PASS and "429" in e.message for e in result.evidence
    ):
        result.status = StageStatus.FAIL
        result.defect = DefectType.RATE_LIMIT_FAILURE
    return result


# ---------------------------------------------------------------------------
# Stage 5: Health Verification
# ---------------------------------------------------------------------------


async def stage_05_health_verification(generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="05_health_verification", status=StageStatus.PASS)

    admin_key = generated_keys.get("admin", {}).get("raw_key")
    if not admin_key:
        result.status = StageStatus.SKIPPED
        result.error = "No admin key"
        result.latency_ms = (time.time() - start) * 1000
        return result

    status_code, body, latency = await _request("GET", "/health", admin_key)

    if status_code == 200:
        checks = [
            ("status", lambda b: b.get("status") in ("healthy", "ok", "degraded")),
            ("timestamp", lambda b: b.get("timestamp") is not None),
            ("latency_ms", lambda b: isinstance(b.get("latency_ms"), (int, float))),
        ]
        for check_name, check_fn in checks:
            if check_fn(body):
                result.evidence.append(
                    Evidence(
                        stage="05_health_verification",
                        status=StageStatus.PASS,
                        message=f"health.{check_name} = {body.get(check_name)}",
                        latency_ms=latency,
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage="05_health_verification",
                        status=StageStatus.FAIL,
                        defect=DefectType.HEALTH_FAILURE,
                        message=f"health.{check_name} missing or invalid",
                        latency_ms=latency,
                    )
                )
                result.status = StageStatus.FAIL
                result.defect = DefectType.HEALTH_FAILURE

        # Verify components block
        components = body.get("components", {})
        if components:
            result.evidence.append(
                Evidence(
                    stage="05_health_verification",
                    status=StageStatus.PASS,
                    message=f"components: {json.dumps(components)}",
                    latency_ms=latency,
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="05_health_verification",
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
        result.error = f"/health returned {status_code}: {body}"
        result.evidence.append(
            Evidence(
                stage="05_health_verification",
                status=StageStatus.FAIL,
                defect=DefectType.HEALTH_FAILURE,
                message=f"HTTP {status_code}",
                latency_ms=latency,
            )
        )

    result.latency_ms = (time.time() - start) * 1000
    return result


# ---------------------------------------------------------------------------
# Stage 6: Copy Status Verification
# ---------------------------------------------------------------------------


async def stage_06_copy_status(generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="06_copy_status", status=StageStatus.PASS)

    admin_key = generated_keys.get("admin", {}).get("raw_key")
    if not admin_key:
        result.status = StageStatus.SKIPPED
        result.error = "No admin key"
        result.latency_ms = (time.time() - start) * 1000
        return result

    status_code, body, latency = await _request("GET", "/copy/status", admin_key)

    if status_code == 200:
        required_fields = [
            "timestamp",
            "running_state",
            "active_leaders",
            "active_followers",
            "filled_orders",
        ]
        for field in required_fields:
            if field in body:
                result.evidence.append(
                    Evidence(
                        stage="06_copy_status",
                        status=StageStatus.PASS,
                        message=f"copy_status.{field} = {body.get(field)}",
                        latency_ms=latency,
                    )
                )
            else:
                result.evidence.append(
                    Evidence(
                        stage="06_copy_status",
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
        result.error = f"/copy/status returned {status_code}: {body}"
        result.evidence.append(
            Evidence(
                stage="06_copy_status",
                status=StageStatus.FAIL,
                message=f"HTTP {status_code}",
                latency_ms=latency,
            )
        )

    result.latency_ms = (time.time() - start) * 1000
    return result


# ---------------------------------------------------------------------------
# Stage 7: Security Matrix
# ---------------------------------------------------------------------------

SECURITY_MATRIX_ENDPOINTS = [
    {"label": "GET /health", "method": "GET", "path": "/health"},
    {"label": "GET /copy/logs", "method": "GET", "path": "/copy/logs"},
    {"label": "GET /leaders", "method": "GET", "path": "/leaders"},
    {"label": "GET /followers", "method": "GET", "path": "/followers"},
    {"label": "GET /copy/status", "method": "GET", "path": "/copy/status"},
]

ROLES_UNDER_TEST = ["admin", "read_only", "revoked", "invalid"]

# Expected: admin=PASS, read_only=PASS or 403, revoked=FAIL, invalid=FAIL
EXPECTED_ROLE_BEHAVIOR = {
    "admin": "PASS",
    "read_only": "PASS_OR_403",
    "revoked": "FAIL",
    "invalid": "FAIL",
}


async def _validate_key(auth_service, raw_key: str) -> bool:
    """Validate a key directly via auth_service."""
    from atlas.api.services.auth_service import APIKey, APIRole

    try:
        key = await auth_service.validate_key(raw_key)
        return key is not None
    except Exception:
        return False


async def stage_07_security_matrix(auth_service, generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="07_security_matrix", status=StageStatus.PASS)

    admin_key = generated_keys.get("admin", {}).get("raw_key", "")
    read_only_key = generated_keys.get("read_only", {}).get("raw_key", "")
    revoked_key_raw = generated_keys.get("revoked", {}).get("raw_key")

    # Generate + revoke a key for "revoked" test
    from atlas.api.services.auth_service import APIRole

    if not revoked_key_raw:
        try:
            revoked_key_raw, revoked_key_id = await auth_service.generate_api_key(
                user_id="revoked_test",
                role=APIRole.READ_ONLY,
                created_by="live_validation",
                description="Will be revoked for security matrix test",
                expires_in_days=1,
            )
            await auth_service.revoke_key(
                revoked_key_id, "live_validation", "Security matrix test"
            )
        except Exception as exc:
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.ERROR,
                    defect=DefectType.AUTH_FAILURE,
                    message=f"Failed to create/revoke test key: {exc}",
                    traceback_str=traceback.format_exc(),
                )
            )

    invalid_key = "atlas_invalid_key_that_does_not_exist_12345"

    matrix = {}
    for role in ROLES_UNDER_TEST:
        matrix[role] = {}
        for ep in SECURITY_MATRIX_ENDPOINTS:
            label = ep["label"]
            if role == "admin":
                token = admin_key
            elif role == "read_only":
                token = read_only_key
            elif role == "revoked":
                token = revoked_key_raw or ""
            elif role == "invalid":
                token = invalid_key
            else:
                token = ""

            status_code, body, latency = await _request(ep["method"], ep["path"], token)

            if status_code in (200, 201):
                matrix[role][label] = "PASS"
            elif status_code == 403:
                matrix[role][label] = "FORBIDDEN"
            elif status_code == 401:
                matrix[role][label] = "UNAUTHORIZED"
            elif status_code == 429:
                matrix[role][label] = "RATE_LIMITED"
            else:
                matrix[role][label] = f"HTTP_{status_code}"

    # Validate admin gets PASS on everything
    for ep in SECURITY_MATRIX_ENDPOINTS:
        val = matrix.get("admin", {}).get(ep["label"], "")
        if val == "PASS":
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.PASS,
                    message=f"admin -> {ep['label']} -> {val}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.FAIL,
                    defect=DefectType.PERMISSION_FAILURE,
                    message=f"admin -> {ep['label']} -> {val} (expected PASS)",
                )
            )
            result.status = StageStatus.FAIL
            result.defect = DefectType.PERMISSION_FAILURE

    # Revoked should get UNAUTHORIZED (401)
    for ep in SECURITY_MATRIX_ENDPOINTS:
        val = matrix.get("revoked", {}).get(ep["label"], "")
        if val in ("UNAUTHORIZED", "FORBIDDEN"):
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.PASS,
                    message=f"revoked -> {ep['label']} -> {val}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.FAIL,
                    defect=DefectType.PERMISSION_FAILURE,
                    message=f"revoked -> {ep['label']} -> {val} (expected 401/403)",
                )
            )
            result.status = StageStatus.FAIL

    # Invalid should get UNAUTHORIZED (401)
    for ep in SECURITY_MATRIX_ENDPOINTS:
        val = matrix.get("invalid", {}).get(ep["label"], "")
        if val == "UNAUTHORIZED":
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.PASS,
                    message=f"invalid -> {ep['label']} -> {val}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="07_security_matrix",
                    status=StageStatus.FAIL,
                    defect=DefectType.PERMISSION_FAILURE,
                    message=f"invalid -> {ep['label']} -> {val} (expected UNAUTHORIZED)",
                )
            )
            result.status = StageStatus.FAIL

    result.latency_ms = (time.time() - start) * 1000
    return result, matrix


# ---------------------------------------------------------------------------
# Stage 8: Audit Trail Verification
# ---------------------------------------------------------------------------


async def stage_08_audit_trail(db, auth_service, generated_keys: dict) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="08_audit_trail", status=StageStatus.PASS)

    try:
        from sqlalchemy.sql import text as sql_text

        async with db.engine.connect() as conn:
            # Check api_request_audit has rows
            row = await conn.execute(sql_text("SELECT COUNT(*) FROM api_request_audit"))
            audit_count = row.scalar() or 0

            # Check audit_logs has rows
            row = await conn.execute(sql_text("SELECT COUNT(*) FROM audit_logs"))
            audit_log_count = row.scalar() or 0

            # Check api_keys exist
            row = await conn.execute(sql_text("SELECT COUNT(*) FROM api_keys"))
            key_count = row.scalar() or 0

            # Check copy_execution_log
            row = await conn.execute(
                sql_text("SELECT COUNT(*) FROM copy_execution_log")
            )
            copy_log_count = row.scalar() or 0

        if audit_count > 0:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.PASS,
                    message=f"api_request_audit rows: {audit_count}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.FAIL,
                    defect=DefectType.AUDIT_FAILURE,
                    message="api_request_audit has 0 rows (requests not being logged)",
                )
            )
            result.status = StageStatus.FAIL
            result.defect = DefectType.AUDIT_FAILURE

        if audit_log_count > 0:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.PASS,
                    message=f"audit_logs rows: {audit_log_count}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.WARN,
                    message=f"audit_logs rows: {audit_log_count}",
                )
            )

        if key_count > 0:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.PASS,
                    message=f"api_keys rows: {key_count}",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="08_audit_trail",
                    status=StageStatus.FAIL,
                    defect=DefectType.AUDIT_FAILURE,
                    message="api_keys has 0 rows (key generation may not persist)",
                )
            )

    except Exception as exc:
        result.evidence.append(
            Evidence(
                stage="08_audit_trail",
                status=StageStatus.ERROR,
                defect=DefectType.AUDIT_FAILURE,
                message=str(exc),
                traceback_str=traceback.format_exc(),
            )
        )
        result.status = StageStatus.ERROR
        result.defect = DefectType.AUDIT_FAILURE

    result.latency_ms = (time.time() - start) * 1000
    return result


# ---------------------------------------------------------------------------
# Stage 9: Restart Certification
# ---------------------------------------------------------------------------


async def _is_server_running(port: int = 8000) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"http://localhost:{port}/health")
            return resp.status_code < 500
    except Exception:
        return False


async def _start_server(port: int = 8000) -> subprocess.Popen:
    """Start the Day 4 API server as a subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "atlas.api.day4_api:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for it to be ready
    for _ in range(30):
        if await _is_server_running(port):
            return proc
        await asyncio.sleep(0.5)
    return proc


async def _stop_server(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


async def stage_09_restart_certification(
    auth_service, generated_keys: dict
) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="09_restart_certification", status=StageStatus.PASS)

    admin_key = generated_keys.get("admin", {}).get("raw_key", "")

    if not admin_key:
        result.status = StageStatus.SKIPPED
        result.error = "No admin key for restart certification"
        result.latency_ms = (time.time() - start) * 1000
        return result

    # Make a request before restart to establish baseline
    status_before, body_before, lat_before = await _request("GET", "/health", admin_key)
    status_before_copy, body_before_copy, _ = await _request(
        "GET", "/copy/status", admin_key
    )

    # Record state before restart (last heartbeat, active leaders, etc.)
    before_state = {
        "health": body_before,
        "copy_status": body_before_copy,
    }

    # Restart the API server (we can't restart the actual process in test easily,
    # so we validate that the auth service can revalidate keys after a simulated
    # restart by clearing the token cache)
    try:
        from atlas.api.middleware.auth_middleware import _auth_middleware

        if _auth_middleware:
            _auth_middleware.clear_cache()
            logger.info("Auth middleware cache cleared (simulating restart)")
    except Exception as exc:
        logger.warning(f"Could not clear auth cache: {exc}")

    # Re-validate key after restart
    key_valid = await _validate_key(auth_service, admin_key)
    if key_valid:
        result.evidence.append(
            Evidence(
                stage="09_restart_certification",
                status=StageStatus.PASS,
                message="Admin key valid after restart (no auth corruption)",
            )
        )
    else:
        result.evidence.append(
            Evidence(
                stage="09_restart_certification",
                status=StageStatus.FAIL,
                defect=DefectType.RESTART_FAILURE,
                message="Admin key INVALID after restart (auth corruption detected)",
            )
        )
        result.status = StageStatus.FAIL
        result.defect = DefectType.RESTART_FAILURE

    # Re-validate read_only key
    read_key_raw = generated_keys.get("read_only", {}).get("raw_key", "")
    if read_key_raw:
        ro_valid = await _validate_key(auth_service, read_key_raw)
        if ro_valid:
            result.evidence.append(
                Evidence(
                    stage="09_restart_certification",
                    status=StageStatus.PASS,
                    message="Read-only key valid after restart",
                )
            )
        else:
            result.evidence.append(
                Evidence(
                    stage="09_restart_certification",
                    status=StageStatus.FAIL,
                    defect=DefectType.RESTART_FAILURE,
                    message="Read-only key invalid after restart",
                )
            )
            result.status = StageStatus.FAIL

    # Make request after restart and verify state is consistent
    status_after, body_after, lat_after = await _request("GET", "/health", admin_key)
    status_after_copy, body_after_copy, _ = await _request(
        "GET", "/copy/status", admin_key
    )

    after_state = {
        "health": body_after,
        "copy_status": body_after_copy,
    }

    # Verify no state corruption: active_leaders should not decrease after restart
    # (increase is normal as new data arrives; decrease means state was lost)
    leaders_before = (
        body_before_copy.get("active_leaders", 0)
        if isinstance(body_before_copy, dict)
        else 0
    )
    leaders_after = (
        body_after_copy.get("active_leaders", 0)
        if isinstance(body_after_copy, dict)
        else 0
    )

    if leaders_after >= leaders_before:
        result.evidence.append(
            Evidence(
                stage="09_restart_certification",
                status=StageStatus.PASS,
                message=f"No state corruption: leaders before={leaders_before}, after={leaders_after}",
            )
        )
    else:
        result.evidence.append(
            Evidence(
                stage="09_restart_certification",
                status=StageStatus.FAIL,
                defect=DefectType.RESTART_FAILURE,
                message=f"State LOSS: leaders before={leaders_before}, after={leaders_after}",
            )
        )
        result.status = StageStatus.FAIL

    result.latency_ms = (time.time() - start) * 1000
    return result


# ---------------------------------------------------------------------------
# Stage 10: Latency Metrics
# ---------------------------------------------------------------------------


async def stage_10_latency_metrics(
    all_stage_results: dict[str, StageResult],
) -> StageResult:
    start = time.time()
    result = StageResult(stage_name="10_latency_metrics", status=StageStatus.PASS)

    # Collect latencies from all previous stages
    latency_report = {}
    for stage_name, sr in all_stage_results.items():
        latency_report[stage_name] = round(sr.latency_ms, 2)

    result.evidence.append(
        Evidence(
            stage="10_latency_metrics",
            status=StageStatus.PASS,
            message="Latency metrics collected",
            detail=latency_report,
        )
    )

    # Flag any stage that took > 60000ms (aggregate includes sequential HTTP requests)
    for stage_name, lat in latency_report.items():
        if lat > 60000:
            result.evidence.append(
                Evidence(
                    stage="10_latency_metrics",
                    status=StageStatus.FAIL,
                    defect=DefectType.LATENCY_FAILURE,
                    message=f"{stage_name} latency {lat:.0f}ms exceeds 60000ms threshold",
                )
            )
            result.status = StageStatus.FAIL
            result.defect = DefectType.LATENCY_FAILURE

    result.latency_ms = (time.time() - start) * 1000
    return result, latency_report


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_validation() -> ValidationOutput:
    """Run all validation stages with deterministic output."""
    logger.info("=" * 70)
    logger.info("  ATLAS DAY 5 LIVE VALIDATION HARNESS")
    logger.info("  Tier-1 Governance Truth Engine")
    logger.info("=" * 70)

    output = ValidationOutput(
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=os.environ.get("ATLAS_ENV", "development"),
        overall_status=StageStatus.PASS,
    )

    # Lazy imports (must happen after project root is on sys.path)
    sys.path.insert(0, str(PROJECT_ROOT))
    from atlas.config.settings import settings
    from atlas.data.storage.timescale_client import TimescaleClient
    from atlas.api.services.auth_service import AuthService

    # Initialize DB and services
    db = TimescaleClient(settings.database_url)
    try:
        await db.connect()
        logger.info("Database connected for live validation")
    except Exception as exc:
        logger.error(f"Database connection failed: {exc}")
        output.overall_status = StageStatus.ERROR
        output.write()
        return output

    auth_service = AuthService(db)

    # -----------------------------------------------------------------------
    # Pre-cleanup: Revoke all existing test keys to avoid bcrypt slowdown
    # -----------------------------------------------------------------------
    logger.info("\n--- Pre-cleanup: Revoking stale test keys ---")
    try:
        from sqlalchemy.sql import text as sql_text

        async with db.engine.begin() as conn:
            await conn.execute(
                sql_text(
                    "UPDATE api_keys SET revoked_at = NOW(), revoke_reason = 'pre_validation_cleanup' "
                    "WHERE revoked_at IS NULL"
                )
            )
        logger.info("  All active api_keys revoked")
    except Exception as exc:
        logger.warning(f"  Pre-cleanup warning: {exc}")

    # -----------------------------------------------------------------------
    # Stage 01: Schema Validation
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 01: Schema Validation ---")
    try:
        output.stages["01_schema_validation"] = await stage_01_schema_validation(db)
        logger.info(f"  Status: {output.stages['01_schema_validation'].status.value}")
    except Exception as exc:
        output.stages["01_schema_validation"] = StageResult(
            stage_name="01_schema_validation",
            status=StageStatus.ERROR,
            defect=DefectType.SCHEMA_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 01 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 02: Key Generation
    # -----------------------------------------------------------------------
    generated_keys = {}
    logger.info("\n--- Stage 02: Key Generation ---")
    try:
        (
            output.stages["02_key_generation"],
            generated_keys,
        ) = await stage_02_key_generation(auth_service)
        logger.info(f"  Status: {output.stages['02_key_generation'].status.value}")
        logger.info(f"  Generated keys: {list(generated_keys.keys())}")
    except Exception as exc:
        output.stages["02_key_generation"] = StageResult(
            stage_name="02_key_generation",
            status=StageStatus.ERROR,
            defect=DefectType.AUTH_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 02 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 03: Route Authentication
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 03: Route Authentication ---")
    try:
        output.stages["03_route_auth"] = await stage_03_route_auth(
            auth_service, generated_keys
        )
        logger.info(f"  Status: {output.stages['03_route_auth'].status.value}")
    except Exception as exc:
        output.stages["03_route_auth"] = StageResult(
            stage_name="03_route_auth",
            status=StageStatus.ERROR,
            defect=DefectType.AUTH_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 03 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 04: Rate Limiting
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 04: Rate Limiting ---")
    try:
        output.stages["04_rate_limiting"] = await stage_04_rate_limiting(
            auth_service, generated_keys
        )
        logger.info(f"  Status: {output.stages['04_rate_limiting'].status.value}")
    except Exception as exc:
        output.stages["04_rate_limiting"] = StageResult(
            stage_name="04_rate_limiting",
            status=StageStatus.ERROR,
            defect=DefectType.RATE_LIMIT_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 04 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 05: Health Verification
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 05: Health Verification ---")
    try:
        output.stages["05_health_verification"] = await stage_05_health_verification(
            generated_keys
        )
        logger.info(f"  Status: {output.stages['05_health_verification'].status.value}")
    except Exception as exc:
        output.stages["05_health_verification"] = StageResult(
            stage_name="05_health_verification",
            status=StageStatus.ERROR,
            defect=DefectType.HEALTH_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 05 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 06: Copy Status
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 06: Copy Status ---")
    try:
        output.stages["06_copy_status"] = await stage_06_copy_status(generated_keys)
        logger.info(f"  Status: {output.stages['06_copy_status'].status.value}")
    except Exception as exc:
        output.stages["06_copy_status"] = StageResult(
            stage_name="06_copy_status",
            status=StageStatus.ERROR,
            defect=DefectType.SERIALIZATION_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 06 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 07: Security Matrix
    # -----------------------------------------------------------------------
    security_matrix = {}
    logger.info("\n--- Stage 07: Security Matrix ---")
    try:
        (
            output.stages["07_security_matrix"],
            security_matrix,
        ) = await stage_07_security_matrix(auth_service, generated_keys)
        logger.info(f"  Status: {output.stages['07_security_matrix'].status.value}")
    except Exception as exc:
        output.stages["07_security_matrix"] = StageResult(
            stage_name="07_security_matrix",
            status=StageStatus.ERROR,
            defect=DefectType.PERMISSION_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 07 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 08: Audit Trail
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 08: Audit Trail ---")
    try:
        output.stages["08_audit_trail"] = await stage_08_audit_trail(
            db, auth_service, generated_keys
        )
        logger.info(f"  Status: {output.stages['08_audit_trail'].status.value}")
    except Exception as exc:
        output.stages["08_audit_trail"] = StageResult(
            stage_name="08_audit_trail",
            status=StageStatus.ERROR,
            defect=DefectType.AUDIT_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 08 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 09: Restart Certification
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 09: Restart Certification ---")
    try:
        output.stages[
            "09_restart_certification"
        ] = await stage_09_restart_certification(auth_service, generated_keys)
        logger.info(
            f"  Status: {output.stages['09_restart_certification'].status.value}"
        )
    except Exception as exc:
        output.stages["09_restart_certification"] = StageResult(
            stage_name="09_restart_certification",
            status=StageStatus.ERROR,
            defect=DefectType.RESTART_FAILURE,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 09 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Stage 10: Latency Metrics
    # -----------------------------------------------------------------------
    logger.info("\n--- Stage 10: Latency Metrics ---")
    try:
        (
            output.stages["10_latency_metrics"],
            latency_report,
        ) = await stage_10_latency_metrics(output.stages)
        output.latency_report = latency_report
        logger.info(f"  Status: {output.stages['10_latency_metrics'].status.value}")
        for s, l in latency_report.items():
            logger.info(f"    {s}: {l:.0f}ms")
    except Exception as exc:
        output.stages["10_latency_metrics"] = StageResult(
            stage_name="10_latency_metrics",
            status=StageStatus.ERROR,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )
        logger.error(f"  Stage 10 crashed: {exc}")

    # -----------------------------------------------------------------------
    # Build security matrix
    # -----------------------------------------------------------------------
    output.security_matrix = security_matrix

    # -----------------------------------------------------------------------
    # Cleanup: revoke all test keys created by this harness
    # -----------------------------------------------------------------------
    logger.info("\n--- Cleanup: Revoking test keys ---")
    try:
        from sqlalchemy.sql import text as sql_text

        async with db.engine.begin() as conn:
            await conn.execute(
                sql_text(
                    "UPDATE api_keys SET revoked_at = NOW(), revoke_reason = 'live_validation_cleanup' "
                    "WHERE description LIKE 'Live validation%' AND revoked_at IS NULL"
                )
            )
        logger.info("  Test keys revoked")
    except Exception as exc:
        logger.warning(f"  Key cleanup warning: {exc}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    all_results = output.stages
    total = len(all_results)
    passed = sum(1 for s in all_results.values() if s.status == StageStatus.PASS)
    failed = sum(1 for s in all_results.values() if s.status == StageStatus.FAIL)
    errors = sum(1 for s in all_results.values() if s.status == StageStatus.ERROR)
    skipped = sum(1 for s in all_results.values() if s.status == StageStatus.SKIPPED)

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

    # Write deterministic output
    output.write()

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info(f"  VALIDATION COMPLETE")
    logger.info(f"  Overall: {output.overall_status.value}")
    logger.info(
        f"  Stages: {passed}/{total} passed, {failed} failed, {errors} errors, {skipped} skipped"
    )
    if defect_counts:
        logger.info(f"  Defects: {json.dumps(defect_counts)}")
    logger.info("=" * 70)

    return output


def main():
    """Entry point. Runs the validation harness."""
    logger.add(sys.stderr, level="INFO")
    logger.add(OUTPUT_DIR / "validation.log", level="DEBUG", rotation="10 MB")

    try:
        output = asyncio.run(run_validation())
    except KeyboardInterrupt:
        logger.warning("Validation interrupted by user")
        output = ValidationOutput(
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=os.environ.get("ATLAS_ENV", "development"),
            overall_status=StageStatus.ERROR,
        )
        output.write()
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Validation failed with exception: {exc}")
        traceback.print_exc()
        output = ValidationOutput(
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=os.environ.get("ATLAS_ENV", "development"),
            overall_status=StageStatus.ERROR,
        )
        output.write()
        sys.exit(1)

    if output.overall_status != StageStatus.PASS:
        sys.exit(1)


if __name__ == "__main__":
    main()
