import sqlite3
from pathlib import Path

db = Path("atlas") / "governance" / "governance.db"
con = sqlite3.connect(str(db))
cur = con.cursor()
tables = [
    'governance_operation_log',
    'governance_decision_log',
    'governance_bypass_events',
    'governance_repair_events',
    'lineage_integrity_failures',
    'trace_continuity_failures',
    'quarantine_registry',
]
for t in tables:
    try:
        cur.execute(f"select count(*) from {t}")
        print(t, cur.fetchone()[0])
    except Exception as e:
        print(t, 'ERROR', e)

for t in ['governance_operation_log','governance_decision_log']:
    try:
        cur.execute(f"select distinct session_id from {t} limit 20")
        print(t, 'sessions:', cur.fetchall())
    except Exception:
        pass

con.close()
