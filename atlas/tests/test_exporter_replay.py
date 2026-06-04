import sqlite3
from atlas.governance import exporter, replay_verifier


def _make_conn_with_rows(rows):
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE governance_operation_log (
        event_id TEXT,
        parent_event_id TEXT,
        root_event_id TEXT,
        governance_state TEXT,
        operation TEXT,
        operation_type TEXT,
        replay_epoch INTEGER,
        operation_hash TEXT,
        timestamp_ns INTEGER,
        interception_stage TEXT,
        operation_sequence INTEGER
    )
    ''')
    cur.executemany('''INSERT INTO governance_operation_log(event_id,parent_event_id,root_event_id,governance_state,operation,operation_type,replay_epoch,operation_hash,timestamp_ns,interception_stage,operation_sequence) VALUES (?,?,?,?,?,?,?,?,?,?,?)''', rows)
    conn.commit()
    return conn


def test_exporter_builds_dag():
    # Create a small chain A -> B -> C
    rows = [
        ('A', '', 'A', 'OBSERVED', 'opA', 'typeA', 0, 'hashA', 1000, 'pre', 1),
        ('B', 'A', 'A', 'OBSERVED', 'opB', 'typeB', 0, 'hashB', 2000, 'pre', 2),
        ('C', 'B', 'A', 'OBSERVED', 'opC', 'typeC', 0, 'hashC', 3000, 'pre', 3),
    ]
    conn = _make_conn_with_rows(rows)
    nodes, edges = exporter.build_dag(conn)
    assert len(nodes) == 3
    assert any(e['src'] == 'A' and e['dst'] == 'B' for e in edges)
    assert any(e['src'] == 'B' and e['dst'] == 'C' for e in edges)


def test_replay_verifier_detects_hash_mismatch():
    rows_canonical = [
        ('A', '', 'A', 'OBSERVED', 'opA', 'typeA', 0, 'hashA', 1000, 'pre', 1),
        ('B', 'A', 'A', 'OBSERVED', 'opB', 'typeB', 0, 'hashB', 2000, 'pre', 2),
    ]
    rows_replay = [
        ('A', '', 'A', 'OBSERVED', 'opA', 'typeA', 0, 'hashA', 1000, 'pre', 1),
        ('B', 'A', 'A', 'OBSERVED', 'opB', 'typeB', 0, 'BADHASH', 2000, 'pre', 2),
    ]
    c = _make_conn_with_rows(rows_canonical)
    r = _make_conn_with_rows(rows_replay)
    res = replay_verifier.verify_replay(c, r)
    assert res.divergence_reason == 'hash_mismatch'


def test_replay_verifier_detects_illegal_transition_in_canonical():
    # Event X moves OBSERVED -> REJECTED -> VALIDATED (illegal: REJECTED -> VALIDATED)
    rows_canonical = [
        ('X', '', 'X', 'OBSERVED', 'op1', 'type', 0, 'h1', 1000, 'pre', 1),
        ('X', '', 'X', 'REJECTED', 'op1', 'type', 0, 'h2', 2000, 'post', 2),
        ('X', '', 'X', 'VALIDATED', 'op1', 'type', 0, 'h3', 3000, 'post', 3),
    ]
    # Replay mirrors canonical (we only care about detecting illegal transition)
    c = _make_conn_with_rows(rows_canonical)
    r = _make_conn_with_rows(rows_canonical)
    res = replay_verifier.verify_replay(c, r)
    assert res.illegal_transition_detected
    assert res.illegal_in_canonical
    assert res.illegal_event_id == 'X'
