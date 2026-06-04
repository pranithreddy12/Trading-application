import json
import pytest
from atlas.governance.runtime import GovernanceRuntimeContext
from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance import hashing
from atlas.core.persistence_integrity import IdentityContractViolation


def test_persist_operation_writes_canonical_event_hash():
    # Use in-memory SQLite for test
    persistence = GovernancePersistenceLayer(db_url="sqlite:///:memory:")
    session_id = persistence.new_session_id()

    event_meta = {
        "event_id": "evt-123",
        "parent_event_id": None,
        "root_event_id": "evt-123",
        "trace_id": "trace-1",
        "strategy_id": "strat-A",
        "operation_sequence": 1,
        "operation_hash": "op-hash-1",
        "event_state": "CREATED",
        "replay_epoch": 0,
    }

    payload = json.dumps({"event_meta": event_meta})

    # Persist operation
    persistence.persist_operation(session_id=session_id, operation="CREATE_RESOURCE", identity_type="CREATE", context="test", payload=payload)

    # Query operation_log for canonical_event_hash
    from sqlalchemy import text
    with persistence.engine.begin() as conn:
        rows = conn.execute(text("SELECT canonical_event_hash, payload FROM governance_operation_log WHERE event_id = :eid"), {"eid": "evt-123"}).fetchall()
    assert len(rows) == 1
    canonical_hash_db = rows[0][0]
    # compute expected
    expected_hash = hashing.event_hash({
        "event_id": event_meta["event_id"],
        "parent_event_id": event_meta.get("parent_event_id"),
        "root_event_id": event_meta.get("root_event_id"),
        "trace_id": event_meta.get("trace_id"),
        "strategy_id": event_meta.get("strategy_id"),
        "operation": "CREATE_RESOURCE",
        "event_state": event_meta.get("event_state"),
        "decision": None,
        "replay_epoch": event_meta.get("replay_epoch"),
        "operation_sequence": event_meta.get("operation_sequence"),
    })

    assert canonical_hash_db == expected_hash


def test_persist_operation_writes_parent_event_hash_for_child():
    persistence = GovernancePersistenceLayer(db_url="sqlite:///:memory:")
    session_id = persistence.new_session_id()

    root_meta = {
        "event_id": "root-1",
        "parent_event_id": None,
        "root_event_id": "root-1",
        "trace_id": "trace-root",
        "strategy_id": "strat-A",
        "operation_sequence": 1,
        "operation_hash": "op-hash-root",
        "event_state": "CREATED",
        "replay_epoch": 0,
    }
    child_meta = {
        "event_id": "child-1",
        "parent_event_id": "root-1",
        "root_event_id": "root-1",
        "trace_id": "trace-child",
        "strategy_id": "strat-A",
        "operation_sequence": 2,
        "operation_hash": "op-hash-child",
        "event_state": "UPDATED",
        "replay_epoch": 0,
    }

    persistence.persist_operation(session_id=session_id, operation="CREATE_RESOURCE", identity_type="CREATE", context="root", payload=json.dumps({"event_meta": root_meta}))
    root_expected = hashing.event_hash({
        "event_id": root_meta["event_id"],
        "parent_event_id": root_meta.get("parent_event_id"),
        "root_event_id": root_meta.get("root_event_id"),
        "trace_id": root_meta.get("trace_id"),
        "strategy_id": root_meta.get("strategy_id"),
        "operation": "CREATE_RESOURCE",
        "event_state": root_meta.get("event_state"),
        "decision": None,
        "replay_epoch": root_meta.get("replay_epoch"),
        "operation_sequence": root_meta.get("operation_sequence"),
    })

    persistence.persist_operation(session_id=session_id, operation="UPDATE_RESOURCE", identity_type="MUTATE", context="child", payload=json.dumps({"event_meta": child_meta}))
    child_expected = hashing.event_hash({
        "event_id": child_meta["event_id"],
        "parent_event_id": child_meta.get("parent_event_id"),
        "root_event_id": child_meta.get("root_event_id"),
        "trace_id": child_meta.get("trace_id"),
        "strategy_id": child_meta.get("strategy_id"),
        "operation": "UPDATE_RESOURCE",
        "event_state": child_meta.get("event_state"),
        "decision": None,
        "replay_epoch": child_meta.get("replay_epoch"),
        "operation_sequence": child_meta.get("operation_sequence"),
    })

    from sqlalchemy import text
    with persistence.engine.begin() as conn:
        rows = conn.execute(text("SELECT canonical_event_hash, parent_event_hash FROM governance_operation_log WHERE event_id = :eid"), {"eid": "child-1"}).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == child_expected
    assert rows[0][1] == root_expected


def test_persist_operation_rejects_missing_parent_hash():
    persistence = GovernancePersistenceLayer(db_url="sqlite:///:memory:")
    session_id = persistence.new_session_id()

    child_meta = {
        "event_id": "child-1",
        "parent_event_id": "missing-parent",
        "root_event_id": "root-1",
        "trace_id": "trace-child",
        "strategy_id": "strat-A",
        "operation_sequence": 2,
        "operation_hash": "op-hash-child",
        "event_state": "UPDATED",
        "replay_epoch": 0,
    }

    with pytest.raises(IdentityContractViolation):
        persistence.persist_operation(session_id=session_id, operation="UPDATE_RESOURCE", identity_type="MUTATE", context="child", payload=json.dumps({"event_meta": child_meta}))


def test_generate_event_identity_populates_causal_identity_fields():
    rt = GovernanceRuntimeContext()
    rt.session_id = "22222222222222222222222222222222"

    event_meta = rt.generate_event_identity(
        "VALIDATE",
        {"field": "id", "value": "x"},
        interception_stage="pre",
    )

    assert event_meta["trace_id"] == rt.session_id
    assert event_meta["lineage_id"] == rt.session_id
    assert event_meta["root_event_id"] == event_meta["event_id"]
    assert event_meta["parent_event_id"] is None
