import os
import json
import pytest

from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.core.persistence_integrity import IdentityContractViolation


def test_strict_enforces_missing_trace_id():
    os.environ["ATLAS_STRICT_IDENTITY_CONTRACTS"] = "1"
    persistence = GovernancePersistenceLayer(db_url="sqlite:///:memory:")
    session_id = persistence.new_session_id()
    event_meta = {
        "event_id": "evt-1",
        "parent_event_id": None,
        "root_event_id": "evt-1",
        # trace_id intentionally missing
        "lineage_id": "11111111-1111-1111-1111-111111111111",
        "operation_sequence": 1,
    }
    payload = json.dumps({"event_meta": event_meta})
    with pytest.raises(IdentityContractViolation):
        persistence.persist_operation(session_id=session_id, operation="OP", identity_type="T", context="c", payload=payload)


def test_non_strict_allows_missing_trace_id():
    os.environ.pop("ATLAS_STRICT_IDENTITY_CONTRACTS", None)
    persistence = GovernancePersistenceLayer(db_url="sqlite:///:memory:")
    session_id = persistence.new_session_id()
    event_meta = {
        "event_id": "evt-2",
        "parent_event_id": None,
        "root_event_id": "evt-2",
        # trace_id missing but not strict
        "lineage_id": "11111111-1111-1111-1111-111111111111",
        "operation_sequence": 1,
    }
    payload = json.dumps({"event_meta": event_meta})
    # Should not raise
    persistence.persist_operation(session_id=session_id, operation="OP", identity_type="T", context="c", payload=payload)
