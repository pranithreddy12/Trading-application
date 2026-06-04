import sqlite3, os
p = os.path.join('atlas', 'governance', 'governance.db')
print('db', p, 'exists', os.path.exists(p))
conn = sqlite3.connect(p)
cur = conn.cursor()
tables = [
    'governance_operation_log',
    'governance_decision_log',
    'governance_bypass_events',
    'governance_repair_events',
    'lineage_integrity_failures',
    'trace_continuity_failures',
    'quarantine_registry',
]
for tbl in tables:
    try:
        cur.execute(f"PRAGMA table_info({tbl})")
        cols = cur.fetchall()
        print('\nTABLE', tbl)
        for c in cols:
            print(c)
    except Exception as e:
        print('ERR', tbl, e)
conn.close()
