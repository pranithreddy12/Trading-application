from __future__ import annotations

import time
import traceback

from ..base_stage import BaseStage
from ..models import StageResult, StageStatus, DefectType, Evidence

DAY4_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL, key_prefix TEXT NOT NULL DEFAULT 'atlas_',
    user_id TEXT NOT NULL, role TEXT NOT NULL,
    scopes JSONB DEFAULT CAST('[]' AS jsonb),
    rate_limit_per_min INT NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'system',
    expires_at TIMESTAMPTZ, last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ, revoked_by TEXT, revoke_reason TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS api_request_audit (
    id BIGSERIAL PRIMARY KEY, api_key_id UUID,
    endpoint TEXT NOT NULL, method TEXT NOT NULL,
    status_code INT NOT NULL, latency_ms INT NOT NULL DEFAULT 0,
    ip_hash TEXT, error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_created ON api_request_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_key ON api_request_audit (api_key_id);
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL, resource_type TEXT NOT NULL,
    resource_id TEXT, actor_id TEXT,
    actor_type TEXT NOT NULL DEFAULT 'api_key',
    status TEXT NOT NULL DEFAULT 'success', reason TEXT,
    old_value JSONB, new_value JSONB,
    status_code INT, error_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs (resource_type, resource_id);
CREATE TABLE IF NOT EXISTS copy_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_order_id TEXT, follower_order_id TEXT,
    leader_id TEXT NOT NULL, follower_id TEXT NOT NULL,
    symbol TEXT NOT NULL, side TEXT NOT NULL,
    leader_qty NUMERIC NOT NULL DEFAULT 0,
    follower_qty NUMERIC NOT NULL DEFAULT 0,
    latency_ms INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending', failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_copy_exec_log_status ON copy_execution_log (status);
CREATE INDEX IF NOT EXISTS idx_copy_exec_log_created ON copy_execution_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_copy_exec_log_symbol ON copy_execution_log (symbol);
CREATE TABLE IF NOT EXISTS copy_leader_accounts (
    leader_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref TEXT NOT NULL, broker TEXT NOT NULL DEFAULT 'paper',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT CAST('{}' AS jsonb)
);
CREATE TABLE IF NOT EXISTS copy_follower_accounts (
    follower_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_id UUID NOT NULL REFERENCES copy_leader_accounts(leader_id),
    account_ref TEXT NOT NULL, broker TEXT NOT NULL DEFAULT 'paper',
    allocation_ratio NUMERIC NOT NULL DEFAULT 1.0,
    max_position_pct NUMERIC NOT NULL DEFAULT 0.1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT CAST('{}' AS jsonb)
);
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref TEXT NOT NULL, symbol TEXT NOT NULL,
    qty NUMERIC NOT NULL DEFAULT 0, avg_price NUMERIC,
    side TEXT NOT NULL DEFAULT 'long',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_positions_account ON positions (account_ref);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions (symbol);
"""

REQUIRED_TABLES = [
    "api_keys",
    "api_request_audit",
    "audit_logs",
    "copy_execution_log",
    "copy_leader_accounts",
    "copy_follower_accounts",
    "positions",
]


class SchemaStage(BaseStage):
    name = "01_schema_validation"

    async def _run(self, ctx) -> StageResult:
        result = StageResult(stage_name=self.name, status=StageStatus.PASS)
        db = ctx.db
        from sqlalchemy.sql import text as sql_text

        async with db.engine.connect() as conn:
            for table in REQUIRED_TABLES:
                ev = Evidence(
                    stage=self.name,
                    status=StageStatus.PASS,
                    message=f"Table {table} exists",
                )
                try:
                    row = await conn.execute(
                        sql_text(
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

        missing = [
            e
            for e in result.evidence
            if e.status in (StageStatus.FAIL, StageStatus.ERROR)
        ]
        if missing:
            await self._bootstrap(db, result)

        post = [
            e
            for e in result.evidence
            if "bootstrapped" in e.message or "exists" in e.message
        ]
        has_failures = any(
            e.status in (StageStatus.FAIL, StageStatus.ERROR) for e in post
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

    async def _bootstrap(self, db, result: StageResult):
        from sqlalchemy.sql import text as sql_text

        for stmt in DAY4_SCHEMA_SQL.split(";"):
            stripped = stmt.strip()
            if stripped and not stripped.startswith("--"):
                try:
                    async with db.engine.begin() as conn:
                        await conn.execute(sql_text(stripped))
                except Exception as exc:
                    pass
        async with db.engine.connect() as conn:
            for table in REQUIRED_TABLES:
                row = await conn.execute(
                    sql_text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
                    ),
                    {"t": table},
                )
                exists = row.scalar()
                if exists:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.PASS,
                            message=f"Table {table} bootstrapped successfully",
                        )
                    )
                else:
                    result.evidence.append(
                        Evidence(
                            stage=self.name,
                            status=StageStatus.FAIL,
                            defect=DefectType.SCHEMA_FAILURE,
                            message=f"Table {table} failed to bootstrap",
                        )
                    )
