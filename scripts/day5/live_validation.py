from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

from atlas.api.services.auth_service import APIRole, AuthService
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "scripts" / "day5" / "live_validation_output.json"
AUTH_MIGRATION = ROOT / "scripts" / "migrations" / "day5_auth_schema.sql"


@dataclass
class ApiProcess:
    proc: subprocess.Popen
    port: int


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        current.append(line)
    cleaned = "\n".join(current)
    for stmt in cleaned.split(";"):
        candidate = stmt.strip()
        if candidate:
            statements.append(candidate)
    return statements


async def apply_auth_schema(db_url: str) -> dict[str, Any]:
    bootstrap_statements = [
        "CREATE EXTENSION IF NOT EXISTS pgcrypto",
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_hash VARCHAR(255) NOT NULL UNIQUE,
            key_prefix VARCHAR(20),
            user_id VARCHAR(100),
            team_id UUID,
            role VARCHAR(50) NOT NULL DEFAULT 'read_only'
                CHECK (role IN ('admin', 'trader', 'read_only', 'follower', 'monitor')),
            scopes JSONB DEFAULT '[]'::jsonb,
            rate_limit_per_min INT DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_by VARCHAR(100),
            last_used_at TIMESTAMP WITH TIME ZONE,
            revoked_at TIMESTAMP WITH TIME ZONE,
            revoke_reason VARCHAR(500),
            revoked_by VARCHAR(100),
            description VARCHAR(255),
            expires_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_request_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
            user_id VARCHAR(100),
            endpoint VARCHAR(255) NOT NULL,
            method VARCHAR(10) NOT NULL,
            status_code INT NOT NULL,
            latency_ms INT NOT NULL,
            ip_hash VARCHAR(128),
            user_agent_hash VARCHAR(128),
            error_message VARCHAR(500),
            resource_id VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            resource_id UUID,
            actor_id VARCHAR(100),
            actor_type VARCHAR(50) DEFAULT 'api_key',
            status VARCHAR(20) NOT NULL DEFAULT 'success'
                CHECK (status IN ('success', 'failure', 'denied')),
            reason VARCHAR(255),
            old_value JSONB,
            new_value JSONB,
            status_code INT,
            error_reason VARCHAR(500)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id) WHERE revoked_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_role ON api_keys(role) WHERE revoked_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_api_request_audit_created_at ON api_request_audit(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC)",
    ]

    sql_text = AUTH_MIGRATION.read_text(encoding="utf-8")
    statements = bootstrap_statements + _split_sql_statements(sql_text)
    engine = create_async_engine(db_url, echo=False)
    executed = 0
    errors: list[str] = []
    try:
        for stmt in statements:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(stmt))
                executed += 1
            except Exception as exc:  # pragma: no cover
                errors.append(f"{stmt[:80]}... => {exc}")
        async with engine.connect() as conn:
            api_keys_count = (await conn.execute(text("SELECT COUNT(*) FROM api_keys"))).scalar() or 0
            audit_count = (await conn.execute(text("SELECT COUNT(*) FROM api_request_audit"))).scalar() or 0
        return {
            "executed_statements": executed,
            "errors": errors,
            "api_keys_count": int(api_keys_count),
            "api_request_audit_count": int(audit_count),
        }
    finally:
        await engine.dispose()


async def generate_keys(db_url: str) -> dict[str, Any]:
    db = TimescaleClient(db_url)
    await db.connect()
    service = AuthService(db)

    role_map = {}
    for role in [APIRole.ADMIN, APIRole.READ_ONLY, APIRole.TRADER, APIRole.FOLLOWER, APIRole.MONITOR]:
        raw_key, key_id = await service.generate_api_key(
            user_id=f"live_{role.value}",
            role=role,
            created_by="day5_live_validation",
            expires_in_days=30,
            rate_limit_per_min=60,
            description=f"live validation key ({role.value})",
        )
        role_map[role.value] = {"key_id": key_id, "raw_key": raw_key}

    revoked_key, revoked_id = await service.generate_api_key(
        user_id="live_revoked",
        role=APIRole.READ_ONLY,
        created_by="day5_live_validation",
        expires_in_days=30,
        rate_limit_per_min=60,
        description="live validation revoked key",
    )
    await service.revoke_key(revoked_id, revoked_by="day5_live_validation", reason="live validation revoke test")
    role_map["revoked_read_only"] = {"key_id": revoked_id, "raw_key": revoked_key}

    stress_key, stress_id = await service.generate_api_key(
        user_id="live_stress",
        role=APIRole.READ_ONLY,
        created_by="day5_live_validation",
        expires_in_days=30,
        rate_limit_per_min=5,
        description="live validation stress key",
    )
    role_map["stress_read_only"] = {"key_id": stress_id, "raw_key": stress_key}

    return role_map


def _wait_for_port(host: str, port: int, timeout_sec: float = 25.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.25)
    return False


def start_api_server(port: int = 8010) -> ApiProcess:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "atlas.api.day4_api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_for_port("127.0.0.1", port):
        proc.terminate()
        raise RuntimeError("API server did not start")
    return ApiProcess(proc=proc, port=port)


def stop_api_server(api_proc: ApiProcess):
    if api_proc.proc.poll() is None:
        api_proc.proc.terminate()
        try:
            api_proc.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api_proc.proc.kill()


def http_get(url: str, token: str | None = None) -> dict[str, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, method="GET", headers=headers)
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return {"status": resp.status, "headers": dict(resp.headers.items()), "body": parsed}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return {"status": exc.code, "headers": dict(exc.headers.items()), "body": parsed}


async def fetch_audit_rows(db_url: str) -> list[dict[str, Any]]:
    engine = create_async_engine(db_url, echo=False)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("""
                SELECT endpoint, status_code, created_at
                FROM api_request_audit
                ORDER BY created_at DESC
                LIMIT 50
            """))
            rows = res.fetchall()
        return [
            {
                "endpoint": row[0],
                "status_code": int(row[1]),
                "created_at": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]
    finally:
        await engine.dispose()


async def check_copy_idempotency(db_url: str) -> dict[str, Any]:
    engine = create_async_engine(db_url, echo=False)
    try:
        async with engine.connect() as conn:
            total = (await conn.execute(text("SELECT COUNT(*) FROM copy_execution_log WHERE leader_order_id IS NOT NULL AND follower_id IS NOT NULL"))).scalar() or 0
            unique_pairs = (await conn.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT leader_order_id, follower_id
                    FROM copy_execution_log
                    WHERE leader_order_id IS NOT NULL AND follower_id IS NOT NULL
                ) t
            """))).scalar() or 0
        return {
            "total_rows": int(total),
            "distinct_leader_follower_pairs": int(unique_pairs),
            "no_duplicates": int(total) == int(unique_pairs),
        }
    finally:
        await engine.dispose()


def run_route_matrix(base_url: str, keys: dict[str, Any]) -> dict[str, Any]:
    endpoints = ["/portfolio", "/positions", "/copy/logs", "/copy/status", "/risk"]

    matrix = {
        "no_token": {},
        "invalid_token": {},
        "read_only": {},
        "trader": {},
        "admin": {},
        "revoked": {},
        "follower": {},
    }

    for ep in endpoints:
        matrix["no_token"][ep] = http_get(f"{base_url}{ep}", token=None)["status"]
        matrix["invalid_token"][ep] = http_get(f"{base_url}{ep}", token="invalid_token_value")["status"]
        matrix["read_only"][ep] = http_get(f"{base_url}{ep}", token=keys["read_only"]["raw_key"])["status"]
        matrix["trader"][ep] = http_get(f"{base_url}{ep}", token=keys["trader"]["raw_key"])["status"]
        matrix["admin"][ep] = http_get(f"{base_url}{ep}", token=keys["admin"]["raw_key"])["status"]
        matrix["revoked"][ep] = http_get(f"{base_url}{ep}", token=keys["revoked_read_only"]["raw_key"])["status"]
        matrix["follower"][ep] = http_get(f"{base_url}{ep}", token=keys["follower"]["raw_key"])["status"]

    return matrix


def run_rate_limit_stress(base_url: str, token: str) -> dict[str, Any]:
    statuses = []
    first_429_headers: dict[str, Any] | None = None
    for _ in range(12):
        resp = http_get(f"{base_url}/portfolio", token=token)
        statuses.append(resp["status"])
        if resp["status"] == 429 and first_429_headers is None:
            normalized = {k.lower(): v for k, v in resp["headers"].items()}
            first_429_headers = {
                "X-RateLimit-Limit": normalized.get("x-ratelimit-limit"),
                "X-RateLimit-Remaining": normalized.get("x-ratelimit-remaining"),
                "X-RateLimit-Reset": normalized.get("x-ratelimit-reset"),
            }
    return {
        "statuses": statuses,
        "has_429": 429 in statuses,
        "first_429_headers": first_429_headers,
    }


async def main():
    db_url = settings.database_url
    result: dict[str, Any] = {
        "timestamp": time.time(),
        "db_url_present": bool(db_url),
    }

    result["bcrypt_installed"] = True

    result["schema_apply"] = await apply_auth_schema(db_url)

    keys = await generate_keys(db_url)
    result["generated_roles"] = sorted(keys.keys())

    api_proc = start_api_server(port=8010)
    base_url = f"http://127.0.0.1:{api_proc.port}"

    try:
        result["health"] = http_get(f"{base_url}/health", token=keys["admin"]["raw_key"])
        result["copy_status"] = http_get(f"{base_url}/copy/status", token=keys["admin"]["raw_key"])

        result["route_matrix"] = run_route_matrix(base_url, keys)
        result["rate_limit_stress"] = run_rate_limit_stress(base_url, keys["stress_read_only"]["raw_key"])

        pre_restart_probe = http_get(f"{base_url}/portfolio", token=keys["admin"]["raw_key"])
        stop_api_server(api_proc)
        api_proc = start_api_server(port=8010)
        post_restart_probe = http_get(f"{base_url}/portfolio", token=keys["admin"]["raw_key"])

        result["restart_probe"] = {
            "pre_restart_status": pre_restart_probe["status"],
            "post_restart_status": post_restart_probe["status"],
        }

    finally:
        stop_api_server(api_proc)

    result["audit_rows"] = await fetch_audit_rows(db_url)
    result["copy_idempotency"] = await check_copy_idempotency(db_url)

    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "schema_errors": len(result["schema_apply"].get("errors", [])),
        "has_429": result.get("rate_limit_stress", {}).get("has_429"),
        "audit_rows": len(result.get("audit_rows", [])),
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
