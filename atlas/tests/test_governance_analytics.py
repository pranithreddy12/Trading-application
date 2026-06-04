from pathlib import Path
import json

from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.analytics import GovernanceAnalyticsEngine


def test_coverage_and_basic_metrics(tmp_path):
    db = tmp_path / "gov.db"
    p = GovernancePersistenceLayer(db_url=f"sqlite:///{db}")
    sid = p.new_session_id()
    # create operation log entries
    for i in range(10):
        p.persist_operation(sid, "VALIDATE", "user", "tests", json.dumps({"i": i}))
    # create bypass and repair events
    p.persist_bypass(sid, "VALIDATE", "shadow", shadow_tag="shadow")
    p.persist_repair(sid, "NORMALIZE", json.dumps({"field":"x"}), json.dumps({"field":"x_fixed"}), shadow_tag="shadow")

    engine = GovernanceAnalyticsEngine(p)
    cov = engine.governance_coverage_percent(sid)
    assert cov >= 0.0
    br = engine.bypass_rate_percent(sid)
    assert br >= 0.0
    rd = engine.repair_dependency_percent(sid)
    assert rd >= 0.0
