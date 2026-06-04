from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Dict, Optional
import importlib

from loguru import logger
from sqlalchemy.sql import text


UUID_PARAM_FIELDS: dict[str, tuple[str, ...]] = {
    "api_keys": ("id",),
    "audit_ledger": ("id", "trace_id"),
    "copy_drift_log": ("id", "trace_id"),
    "copy_execution_log": ("id",),
    "copy_follower_accounts": ("follower_id", "leader_id"),
    "copy_leader_accounts": ("leader_id",),
    "economic_efficiency_analysis": ("id",),
    "economic_fitness_windows": ("id",),
    "event_snapshots": ("id", "aggregate_id"),
    "event_store": ("id", "trace_id", "parent_event_id", "aggregate_id"),
    "lifecycle_events": ("id", "trace_id", "strategy_id", "parent_event_id"),
    "mutation_lineage_log": ("id",),
    "mutation_memory": ("id", "parent_strategy_id", "child_strategy_id"),
    "organism_regime_profile": ("id", "strategy_id"),
    "portfolio_evolution_log": ("id",),
    "regime_specialization_aggregate": ("id",),
    "regime_specialization_log": ("id", "analysis_id"),
    "regime_specialization_summary": ("id", "analysis_id"),
    "replay_integrity": ("id",),
    "scout_divergence_log": ("id",),
    "scout_predictive_value_log": ("id", "analysis_id"),
    "strategies": ("id", "trace_id"),
    "system_health": ("id",),
}

DEFAULT_UUID_FIELDS: tuple[str, ...] = (
    "id",
    "trace_id",
    "event_id",
    "snapshot_id",
    "analysis_id",
    "lineage_id",
    "strategy_id",
    "parent_strategy_id",
    "child_strategy_id",
    "parent_event_id",
    "aggregate_id",
)

STRICT_IDENTITY_CONTRACT_ENV = "ATLAS_STRICT_IDENTITY_CONTRACTS"

# Core identities represent lineage truth rather than convenience identifiers.
# In strict mode these fields must be rejected instead of repaired.
STRICT_IDENTITY_FIELDS: tuple[str, ...] = (
    "trace_id",
    "lineage_id",
    "strategy_id",
    "parent_strategy_id",
    "child_strategy_id",
    "parent_event_id",
    "aggregate_id",
)

STRICT_IDENTITY_FIELDS_BY_TABLE: dict[str, tuple[str, ...]] = {
    "audit_ledger": ("id", "trace_id"),
    "event_snapshots": ("id", "aggregate_id"),
    "event_store": ("id", "trace_id", "parent_event_id", "aggregate_id"),
    "lifecycle_events": ("id", "trace_id", "strategy_id", "parent_event_id"),
    "mutation_lineage_log": ("id",),
    "mutation_memory": ("id", "parent_strategy_id", "child_strategy_id"),
    "organism_regime_profile": ("id", "strategy_id"),
    "regime_specialization_aggregate": ("id",),
    "regime_specialization_log": ("id", "analysis_id"),
    "regime_specialization_summary": ("id", "analysis_id"),
    "replay_integrity": ("id",),
    "scout_divergence_log": ("id",),
    "scout_predictive_value_log": ("id", "analysis_id"),
    "strategies": ("id", "trace_id"),
}


class IdentityContractViolation(RuntimeError):
    """Raised when strict identity governance rejects a UUID repair."""


def strict_identity_contracts_enabled() -> bool:
    """Return True when core IDs must be rejected instead of repaired."""

    return os.getenv(STRICT_IDENTITY_CONTRACT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_strict_identity_field(field_name: str, table_name: str | None = None) -> bool:
    if field_name in STRICT_IDENTITY_FIELDS:
        return True
    if table_name:
        return field_name in STRICT_IDENTITY_FIELDS_BY_TABLE.get(table_name.lower(), ())
    return False


@dataclass(frozen=True)
class IdentityEnvelope:
    """Encapsulates identity values as governed entities.

    Use `IdentityEnvelope.from_raw()` to validate and construct via governance.
    """

    id: str
    identity_type: str
    origin_service: Optional[str] = None
    parent_identity: Optional[str] = None
    lineage_root: Optional[str] = None
    trace_context: Optional[Dict[str, Any]] = None
    creation_timestamp: Optional[str] = None
    immutable: bool = True

    @classmethod
    def from_raw(cls, raw: Any, *, field_name: str, context: str = "") -> "IdentityEnvelope":
        canonical = canonical_uuid(raw, field_name=field_name, context=context)
        return cls(id=canonical, identity_type=field_name, creation_timestamp=None)


# Governance engine singletons (lazily instantiated)
_GOV_RUNTIME = None
_GOV_JOURNAL = None
_GOV_ENGINE = None


def _get_governance_engine():
    """Lazily import and return a governance engine instance.

    Returns None if governance package cannot be imported.
    """
    global _GOV_RUNTIME, _GOV_JOURNAL, _GOV_ENGINE
    if _GOV_ENGINE is not None:
        return _GOV_ENGINE
    try:
        gov = importlib.import_module("atlas.governance")
        # initialize runtime with current strictness
        _GOV_RUNTIME = gov.GovernanceRuntimeContext(strict_mode=strict_identity_contracts_enabled())
        _GOV_JOURNAL = gov.IdentityViolationJournal()
        _GOV_ENGINE = gov.GovernanceViolationEngine(_GOV_RUNTIME, _GOV_JOURNAL)
        return _GOV_ENGINE
    except Exception:
        # Governance optional: if not available, return None silently
        return None


@dataclass(frozen=True)
class SchemaContract:
    name: str
    required_tables: tuple[str, ...] = ()
    required_columns: dict[str, tuple[str, ...]] = field(default_factory=dict)
    migration_guidance: str = ""


@dataclass
class SchemaValidationReport:
    valid: bool = True
    checked_contracts: list[str] = field(default_factory=list)
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    guidance: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "checked_contracts": list(self.checked_contracts),
            "missing_tables": list(self.missing_tables),
            "missing_columns": {k: list(v) for k, v in self.missing_columns.items()},
            "guidance": list(self.guidance),
        }


def canonical_uuid(
    value: Any,
    *,
    field_name: str,
    context: str = "",
    allow_generate: bool = True,
    strict: bool | None = None,
    operation: str | None = None,
    exec_context: dict | None = None,
) -> str:
    """Validate an identifier and return a canonical UUIDv4 string."""
    strict_mode = strict_identity_contracts_enabled() if strict is None else strict
    is_strict_identity = _is_strict_identity_field(field_name)

    # governance engine (optional)
    gov = _get_governance_engine()
    # track identity operation totals and bypasses
    try:
        if _GOV_RUNTIME is not None:
            _GOV_RUNTIME.increment_metric("identity_operations_total")
            if gov is not None:
                _GOV_RUNTIME.increment_metric("identity_operations_governed")
        else:
            # no governance runtime: count as bypass
            if _GOV_RUNTIME is None and gov is None:
                # best-effort: attempt to import runtime from governance package
                pass
    except Exception:
        pass
    op_type = None
    try:
        from atlas.governance.context import IdentityOperationType, GovernanceExecutionContext

        op_type = IdentityOperationType(operation) if operation else IdentityOperationType.VALIDATE
        exec_ctx = GovernanceExecutionContext(**exec_context) if exec_context else None
        # detect callers that don't provide semantic operation as potential bypasses
        if op_type is IdentityOperationType.VALIDATE and _GOV_RUNTIME is not None:
            _GOV_RUNTIME.increment_metric("bypass_attempts")
    except Exception:
        op_type = None
        exec_ctx = None

    if value is None or value == "":
        # missing identity
        payload = {"type": "missing_identity", "field": field_name, "context": context or "unknown"}
        if gov and op_type:
            gov.before_identity_operation(op_type, payload, exec_ctx)

        if not allow_generate or (strict_mode and is_strict_identity):
            # after hook records the rejection
            if gov and op_type:
                try:
                    gov.after_identity_operation(op_type, payload, gov.evaluate(payload), exec_ctx)
                except Exception:
                    pass
            raise IdentityContractViolation(
                f"Missing UUID field '{field_name}' in {context or 'unknown context'}"
            )
        recovered = str(uuid.uuid4())
        logger.warning(
            f"UUID normalization: generated new value for missing field '{field_name}' in {context or 'unknown context'} -> {recovered}"
        )
        if gov and op_type:
            gov.after_identity_operation(op_type, {**payload, "value": recovered}, gov.evaluate({**payload, "value": recovered}), exec_ctx, snapshot={"recovered": recovered})
        return recovered

    candidate = str(value)
    try:
        val = str(uuid.UUID(candidate))
        payload = {"type": "validated", "field": field_name, "context": context or "unknown", "value": val}
        if gov and op_type:
            gov.before_identity_operation(op_type, payload, exec_ctx)
            # after successful validation
            gov.after_identity_operation(op_type, payload, gov.evaluate(payload), exec_ctx, snapshot={"validated": val})
        return val
    except Exception:
        payload = {"type": "invalid_identity", "field": field_name, "context": context or "unknown", "value": candidate}
        if gov and op_type:
            try:
                gov.before_identity_operation(op_type, payload, exec_ctx)
            except IdentityContractViolation:
                # before hook will have raised; propagate
                raise
        if not allow_generate or (strict_mode and is_strict_identity):
            if gov and op_type:
                try:
                    gov.after_identity_operation(op_type, payload, gov.evaluate(payload), exec_ctx)
                except Exception:
                    pass
            raise IdentityContractViolation(
                f"Invalid UUID field '{field_name}' in {context or 'unknown context'} ({candidate})"
            )
        recovered = str(uuid.uuid4())
        logger.warning(
            f"UUID normalization: recovered invalid field '{field_name}' in {context or 'unknown context'} ({candidate}) -> {recovered}"
        )
        if gov and op_type:
            gov.after_identity_operation(op_type, {**payload, "recovered": recovered}, gov.evaluate({**payload, "recovered": recovered}), exec_ctx, snapshot={"recovered": recovered})
        return recovered


def normalize_uuid_params(
    params: dict[str, Any],
    *,
    table_name: str,
    context: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Normalize known UUID fields for a specific table before insert."""

    normalized = dict(params)
    recovered_fields: list[str] = []
    table_key = table_name.lower()
    fields = tuple(dict.fromkeys(DEFAULT_UUID_FIELDS + UUID_PARAM_FIELDS.get(table_key, ())))
    if not fields:
        return normalized, recovered_fields

    strict_table_fields = set(STRICT_IDENTITY_FIELDS_BY_TABLE.get(table_key, ()))
    strict_mode_global = strict_identity_contracts_enabled()

    for field_name in fields:
        if field_name not in normalized:
            continue
        before = normalized[field_name]
        is_field_strict = _is_strict_identity_field(field_name, table_name) or field_name in strict_table_fields
        allow_generate = not (strict_mode_global and is_field_strict)
        after = canonical_uuid(
            before,
            field_name=field_name,
            context=f"{context}:{table_name}" if context else table_name,
            strict=strict_mode_global,
            allow_generate=allow_generate,
        )
        if str(before) != after:
            recovered_fields.append(field_name)
            normalized[field_name] = after

    return normalized, recovered_fields


DEFAULT_SCHEMA_CONTRACTS: tuple[SchemaContract, ...] = (
    SchemaContract(
        name="core_auth_copy",
        required_tables=(
            "api_keys",
            "api_request_audit",
            "audit_logs",
            "copy_execution_log",
            "copy_leader_accounts",
            "copy_follower_accounts",
            "positions",
        ),
        required_columns={
            "api_keys": (
                "id",
                "key_hash",
                "key_prefix",
                "user_id",
                "role",
                "scopes",
                "rate_limit_per_min",
                "is_active",
                "created_at",
                "revoked_at",
            ),
            "copy_execution_log": (
                "id",
                "leader_order_id",
                "follower_order_id",
                "leader_id",
                "follower_id",
                "symbol",
                "side",
                "leader_qty",
                "follower_qty",
                "latency_ms",
                "status",
                "created_at",
            ),
        },
        migration_guidance="Run the Day 4 bootstrap SQL or scripts/run_migration.py to restore core auth/copy tables.",
    ),
    SchemaContract(
        name="event_lineage_and_replay",
        required_tables=(
            "event_store",
            "event_snapshots",
            "audit_ledger",
            "lifecycle_events",
            "failed_inserts",
            "schema_version",
            "mutation_memory",
        ),
        required_columns={
            "event_store": (
                "id",
                "aggregate_id",
                "aggregate_type",
                "event_type",
                "version",
                "data",
                "trace_id",
                "parent_event_id",
                "created_at",
                "sequence",
                "metadata",
                "hash_prev",
                "hash_self",
            ),
            "audit_ledger": (
                "id",
                "event_type",
                "actor",
                "action",
                "resource_type",
                "resource_id",
                "details",
                "severity",
                "trace_id",
                "sequence",
                "hash_prev",
                "hash_self",
                "created_at",
            ),
            "mutation_memory": (
                "id",
                "parent_strategy_id",
                "child_strategy_id",
                "mutation_type",
                "changed_fields",
                "parent_sharpe",
                "child_sharpe",
                "sharpe_delta",
                "parent_entry_count",
                "child_entry_count",
                "parent_trades",
                "child_trades",
                "created_at",
                "parent_composite_score",
                "child_composite_score",
                "score_delta",
                "improved",
            ),
        },
        migration_guidance="Run the replay/event lineage migration or atlas/data/storage schema bootstrap before starting agents.",
    ),
    SchemaContract(
        name="phase31_specialization",
        required_tables=(
            "dominant_organism_log",
            "mutation_lineage_log",
            "organism_regime_profile",
            "regime_specialization_aggregate",
            "scout_divergence_log",
            "portfolio_evolution_log",
            "regime_specialization_log",
            "regime_specialization_summary",
            "scout_predictive_value_log",
            "phase31_specialization_metrics",
        ),
        required_columns={
            "portfolio_evolution_log": (
                "id",
                "tracked_at",
                "created_at",
                "portfolio_id",
                "diversification_score",
                "correlation_collapse_risk",
                "contagion_exposure",
                "concentration_risk",
                "portfolio_survivability",
                "drawdown_recovery_speed",
                "active_strategies",
                "metadata",
            ),
            "mutation_lineage_log": (
                "id",
                "tracked_at",
                "n_mutations_analyzed",
                "n_lineages_identified",
                "n_dominant_lineages",
                "lineages",
                "survival_rates",
                "regime_specialization",
                "drawdown_behavior",
                "dominant_lineages",
                "ecosystem_stats",
                "metadata",
            ),
            "scout_divergence_log": (
                "id",
                "tracked_at",
                "n_attributions_analyzed",
                "n_scouts_tracked",
                "profit_contribution",
                "failure_contribution",
                "regime_usefulness",
                "contradiction_penalties",
                "attribution_quality",
                "divergence_scores",
                "ecosystem_scout_health",
                "metadata",
            ),
        },
        migration_guidance="Run atlas/scripts/phase31_db_migration.py to refresh the specialization persistence schema.",
    ),
)


class SchemaContractRegistry:
    def __init__(self, contracts: Iterable[SchemaContract] | None = None):
        self.contracts = tuple(contracts or DEFAULT_SCHEMA_CONTRACTS)

    @classmethod
    def default(cls) -> "SchemaContractRegistry":
        return cls(DEFAULT_SCHEMA_CONTRACTS)

    async def validate(self, db) -> SchemaValidationReport:
        report = SchemaValidationReport()
        async with db.engine.connect() as conn:
            for contract in self.contracts:
                report.checked_contracts.append(contract.name)

                for table in contract.required_tables:
                    row = await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
                        ),
                        {"table_name": table},
                    )
                    exists = bool(row.scalar())
                    if not exists:
                        report.valid = False
                        report.missing_tables.append(table)
                        if contract.migration_guidance not in report.guidance:
                            report.guidance.append(contract.migration_guidance)

                for table_name, columns in contract.required_columns.items():
                    row = await conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = :table_name"
                        ),
                        {"table_name": table_name},
                    )
                    actual = {str(r[0]) for r in row.fetchall()}
                    missing = [column for column in columns if column not in actual]
                    if missing:
                        report.valid = False
                        report.missing_columns[table_name] = missing
                        if contract.migration_guidance not in report.guidance:
                            report.guidance.append(contract.migration_guidance)

        if not report.valid:
            logger.warning(
                f"Schema contract validation failed: tables={report.missing_tables} columns={report.missing_columns}"
            )
            for guidance in report.guidance:
                logger.warning(f"Schema guidance: {guidance}")
        else:
            logger.info(f"Schema contract validation passed for {len(self.contracts)} contracts")

        return report
