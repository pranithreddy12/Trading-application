from __future__ import annotations

import uuid

import pytest

from atlas.core.persistence_integrity import (
    IdentityContractViolation,
    SchemaContractRegistry,
    canonical_uuid,
    normalize_uuid_params,
)


def test_canonical_uuid_recovers_invalid_value() -> None:
    recovered = canonical_uuid(
        "not-a-uuid",
        field_name="trace_id",
        context="unit_test",
    )

    parsed = uuid.UUID(recovered)
    assert str(parsed) == recovered


def test_normalize_uuid_params_preserves_business_refs() -> None:
    normalized, recovered_fields = normalize_uuid_params(
        {
            "id": "truncated",
            "leader_id": "leader_atlas_001",
            "follower_id": "follower_atlas_002",
            "symbol": "SPY",
        },
        table_name="copy_execution_log",
        context="unit_test",
    )

    assert "id" in recovered_fields
    assert normalized["leader_id"] == "leader_atlas_001"
    assert normalized["follower_id"] == "follower_atlas_002"
    uuid.UUID(normalized["id"])


def test_schema_contract_registry_includes_phase31_portfolio_columns() -> None:
    registry = SchemaContractRegistry.default()
    phase31 = next(contract for contract in registry.contracts if contract.name == "phase31_specialization")

    assert "portfolio_evolution_log" in phase31.required_columns
    assert "contagion_exposure" in phase31.required_columns["portfolio_evolution_log"]
    assert "created_at" in phase31.required_columns["portfolio_evolution_log"]


def test_strict_identity_contract_rejects_core_trace_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_STRICT_IDENTITY_CONTRACTS", "1")

    with pytest.raises(IdentityContractViolation):
        canonical_uuid(
            "not-a-uuid",
            field_name="trace_id",
            context="unit_test",
        )


def test_strict_identity_contract_rejects_lineage_table_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_STRICT_IDENTITY_CONTRACTS", "1")

    with pytest.raises(IdentityContractViolation):
        normalize_uuid_params(
            {
                "id": "truncated",
                "parent_strategy_id": "bad-parent",
                "child_strategy_id": "bad-child",
            },
            table_name="mutation_memory",
            context="unit_test",
        )
