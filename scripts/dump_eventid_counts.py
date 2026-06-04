import sqlite3, os
p = os.path.join('atlas','governance','governance.db')
print('db', p, 'exists', os.path.exists(p))
conn = sqlite3.connect(p)
cur = conn.cursor()
seq = ['governance_operation_log','governance_decision_log','governance_bypass_events','governance_repair_events','lineage_integrity_failures','trace_continuity_failures','quarantine_registry']
for t in seq:
    try:
        cur.execute(f"SELECT COUNT(DISTINCT event_id) FROM {t}")
        c = cur.fetchone()[0]
        print(t, c)
    except Exception as e:
        print('ERR', t, e)
all_ids = set()
for t in seq:
    try:
        cur.execute(f"SELECT DISTINCT event_id FROM {t} WHERE event_id IS NOT NULL")
        for r in cur.fetchall():
            all_ids.add(r[0])
    except Exception:
        pass
print('union', len([i for i in all_ids if i]))
gov = set()
for t in ('governance_decision_log','governance_bypass_events','governance_repair_events'):
    try:
        cur.execute(f"SELECT DISTINCT event_id FROM {t} WHERE event_id IS NOT NULL")
        for r in cur.fetchall():
            gov.add(r[0])
    except Exception:
        pass
print('governed', len([i for i in gov if i]))
conn.close()
