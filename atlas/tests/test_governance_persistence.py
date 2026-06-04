import json
import os
from pathlib import Path

import pytest

from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.reporter import GovernanceMetricsReporter


def test_persistence_layer_basic(tmp_path):
    db_file = tmp_path / "gov.db"
    db_url = f"sqlite:///{db_file}"
    p = GovernancePersistenceLayer(db_url=db_url)
    sid = p.new_session_id()

    # persist an operation and a decision
    p.persist_operation(sid, "VALIDATE", "user", "tests", json.dumps({"id": "x"}))
    p.persist_decision(sid, "ALLOW", "INFO", "no-violation")
    p.persist_bypass(sid, "VALIDATE", "shadow-detected", shadow_tag="shadow")
    p.persist_repair(sid, "NORMALIZE", "orig", "fixed", shadow_tag="shadow")
    p.persist_lineage_failure(sid, "tracker", "missing lineage_id")
    p.persist_trace_failure(sid, "propagator", "trace broken")
    p.persist_quarantine(sid, "res-1", "suspicious", shadow_tag="shadow")

    # counts
    assert p.query_counts(p.operation_log, sid) == 1
    assert p.query_counts(p.decision_log, sid) >= 1
    assert p.query_counts(p.bypass_events, sid) == 1
    assert p.query_counts(p.repair_events, sid) == 1
    assert p.query_counts(p.lineage_failures, sid) == 1
    assert p.query_counts(p.trace_failures, sid) == 1
    assert p.query_counts(p.quarantine, sid) == 1


def test_reporter_generates_summary(tmp_path):
    db_file = tmp_path / "gov2.db"
    db_url = f"sqlite:///{db_file}"
    p = GovernancePersistenceLayer(db_url=db_url)
    sid = p.new_session_id()

    # write some operations
    for i in range(5):
        p.persist_operation(sid, "VALIDATE", "user", "tests", json.dumps({"i": i}))
    for i in range(3):
        p.persist_operation(sid, "NORMALIZE", "user", "tests", json.dumps({"i": i}))

    p.persist_decision(sid, "REPAIR", "WARNING", "repaired")
    p.persist_bypass(sid, "NORMALIZE", "shadow", shadow_tag="shadow")

    r = GovernanceMetricsReporter(p)
    summary = r.governance_summary(sid)
    assert "operations" in summary
    assert summary["operations"].get("VALIDATE") == 5
    assert summary["operations"].get("NORMALIZE") == 3
