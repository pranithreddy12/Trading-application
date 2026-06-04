import os
import uuid
import pytest

from atlas.core.persistence_integrity import normalize_uuid_params, IdentityContractViolation


def test_normalize_uuid_params_non_strict_recovers():
    # ensure non-strict mode recovers invalid/missing UUIDs
    os.environ.pop("ATLAS_STRICT_IDENTITY_CONTRACTS", None)
    params = {"id": "", "trace_id": "not-a-uuid"}
    normalized, recovered = normalize_uuid_params(params, table_name="event_store", context="unit_test")
    assert "id" in recovered or "trace_id" in recovered
    assert uuid.UUID(normalized["id"])  # valid uuid
    assert uuid.UUID(normalized["trace_id"])  # valid uuid


def test_normalize_uuid_params_strict_rejects_missing_trace():
    os.environ["ATLAS_STRICT_IDENTITY_CONTRACTS"] = "true"
    params = {"id": str(uuid.uuid4()), "trace_id": ""}
    with pytest.raises(IdentityContractViolation):
        normalize_uuid_params(params, table_name="event_store", context="unit_test")


def test_normalize_uuid_params_strict_rejects_invalid_trace():
    os.environ["ATLAS_STRICT_IDENTITY_CONTRACTS"] = "1"
    params = {"id": str(uuid.uuid4()), "trace_id": "invalid-uuid"}
    with pytest.raises(IdentityContractViolation):
        normalize_uuid_params(params, table_name="event_store", context="unit_test")
