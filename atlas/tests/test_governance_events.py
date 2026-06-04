import json

from atlas.governance.runtime import GovernanceRuntimeContext
from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.analytics import GovernanceAnalyticsEngine


def test_event_id_determinism():
    rt1 = GovernanceRuntimeContext()
    rt1.session_id = "deadbeefdeadbeefdeadbeefdeadbeef"
    em1 = rt1.generate_event_identity("VALIDATE", {"field": "id", "value": "x"}, "pre")
    seq = em1["operation_sequence"]

    rt2 = GovernanceRuntimeContext()
    rt2.session_id = rt1.session_id
    # set sequence so next generated sequence matches
    rt2._sequence_counter = seq - 1
    em2 = rt2.generate_event_identity("VALIDATE", {"field": "id", "value": "x"}, "pre")

    assert em1["event_id"] == em2["event_id"]
    assert em1["operation_hash"] == em2["operation_hash"]


def test_coverage_dedupes_event_ids(tmp_path):
    # persistence layer uses file-based sqlite; point it to a temp file
    db_path = tmp_path / "govtest.db"
    g = GovernancePersistenceLayer(db_url=f"sqlite:///{db_path}")
    session_id = g.new_session_id()

    rt = GovernanceRuntimeContext()
    rt.session_id = session_id

    # generate an event_meta
    em = rt.generate_event_identity("VALIDATE", {"field": "id", "value": "x"}, "pre")

    payload = {"example": True, "event_meta": em}
    payload_str = json.dumps(payload)

    # persist operation twice with same event_meta (duplicate events)
    g.persist_operation(session_id, "VALIDATE", "id", "ctx", payload_str)
    g.persist_operation(session_id, "VALIDATE", "id", "ctx", payload_str)
    # also persist a decision for the same event to mark it as governed
    g.persist_decision(session_id, "ALLOW", "INFO", "test-violation", event_meta=em)

    ae = GovernanceAnalyticsEngine(g, journal_path=tmp_path / "journal.log")
    cov = ae.governance_coverage_percent(session_id)

    # total unique ops should be 1, so coverage is 100.0
    assert cov == 100.0
