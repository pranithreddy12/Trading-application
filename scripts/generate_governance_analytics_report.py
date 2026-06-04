from __future__ import annotations

import json
from pathlib import Path

from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.analytics import GovernanceAnalyticsEngine


def main():
    p = GovernancePersistenceLayer()
    # find latest session (reuse script from generate_governance_audit_report)
    from atlas.governance.persistence import GovernancePersistenceLayer as GPL
    from sqlalchemy import select, func

    dl = p.decision_log
    s = select(dl.c.session_id, func.max(dl.c.timestamp).label("ts")).group_by(dl.c.session_id).order_by(func.max(dl.c.timestamp).desc()).limit(1)
    with p.engine.begin() as conn:
        rows = conn.execute(s).fetchall()
    sid = None
    if rows:
        sid = rows[0][0]
    else:
        op = p.operation_log
        s2 = select(op.c.session_id, func.max(op.c.timestamp).label("ts")).group_by(op.c.session_id).order_by(func.max(op.c.timestamp).desc()).limit(1)
        with p.engine.begin() as conn:
            rows2 = conn.execute(s2).fetchall()
        if rows2:
            sid = rows2[0][0]

    if not sid:
        print("No sessions to analyze")
        return 1

    engine = GovernanceAnalyticsEngine(p)
    metrics = engine.compute_all(sid)

    out_dir = Path(__file__).resolve().parent.parent / "atlas" / "governance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"governance_analytics_{sid}.json"
    out_file.write_text(json.dumps(metrics, indent=2))
    print("Analytics persisted to:", out_file)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
