from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.reporter import GovernanceMetricsReporter


def latest_session(persist: GovernancePersistenceLayer) -> str | None:
    dl = persist.decision_log
    from sqlalchemy import select, func
    # prefer decision_log, fallback to operation_log
    s = select(dl.c.session_id, func.max(dl.c.timestamp).label("ts")).group_by(dl.c.session_id).order_by(func.max(dl.c.timestamp).desc()).limit(1)
    with persist.engine.begin() as conn:
        rows = conn.execute(s).fetchall()
    if not rows:
        # fallback to operation log sessions
        op = persist.operation_log
        s2 = select(op.c.session_id, func.max(op.c.timestamp).label("ts")).group_by(op.c.session_id).order_by(func.max(op.c.timestamp).desc()).limit(1)
        with persist.engine.begin() as conn:
            rows2 = conn.execute(s2).fetchall()
        if not rows2:
            return None
        return rows2[0][0]
    return rows[0][0]


def main():
    p = GovernancePersistenceLayer()
    sid = latest_session(p)
    if not sid:
        print("No governance sessions found in DB.")
        return 1

    reporter = GovernanceMetricsReporter(p)
    summary = reporter.governance_summary(sid)
    out_dir = Path(__file__).resolve().parent.parent / "atlas" / "governance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"governance_audit_report_{sid}.json"
    payload = {
        "session_id": sid,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
    }
    out_file.write_text(json.dumps(payload, indent=2))
    print("Audit report written to:", out_file)
    print(json.dumps({"session_id": sid, "operations": summary.get("operations", {}), "top_violations": summary.get("top_violations", [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
