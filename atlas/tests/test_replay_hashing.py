import sqlite3
import time

from atlas.governance import replay_verifier


def _make_db(rows):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE governance_operation_log (
            event_id TEXT,
            parent_event_id TEXT,
            root_event_id TEXT,
            operation TEXT,
            decision TEXT,
            trace_id TEXT,
            strategy_id TEXT,
            operation_hash TEXT,
            operation_sequence INTEGER,
            governance_state TEXT,
            timestamp_ns INTEGER
        )
        """
    )
    for r in rows:
        cur.execute(
            "INSERT INTO governance_operation_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.get("event_id"),
                r.get("parent_event_id"),
                r.get("root_event_id"),
                r.get("operation"),
                r.get("decision"),
                r.get("trace_id"),
                r.get("strategy_id"),
                r.get("operation_hash"),
                r.get("operation_sequence"),
                r.get("governance_state"),
                r.get("timestamp_ns"),
            ),
        )
    conn.commit()
    return conn


def test_stream_hash_matches_for_identical_streams():
    ts = int(time.time() * 1e9)
    rows = [
        {"event_id": "e1", "operation_hash": "h1", "operation_sequence": 1, "governance_state": "CREATED", "timestamp_ns": ts},
        {"event_id": "e2", "operation_hash": "h2", "operation_sequence": 2, "governance_state": "UPDATED", "timestamp_ns": ts + 1},
    ]
    cdb = _make_db(rows)
    rdb = _make_db(rows)

    res = replay_verifier.verify_replay(cdb, rdb)
    assert res.canonical_hash is not None
    assert res.replay_hash is not None
    assert res.canonical_hash == res.replay_hash


def test_stream_hash_differs_for_reordered_streams():
    ts = int(time.time() * 1e9)
    rows_c = [
        {"event_id": "e1", "operation_hash": "h1", "operation_sequence": 1, "governance_state": "CREATED", "timestamp_ns": ts},
        {"event_id": "e2", "operation_hash": "h2", "operation_sequence": 2, "governance_state": "UPDATED", "timestamp_ns": ts + 1},
    ]
    rows_r = [
        {"event_id": "e2", "operation_hash": "h2", "operation_sequence": 1, "governance_state": "UPDATED", "timestamp_ns": ts},
        {"event_id": "e1", "operation_hash": "h1", "operation_sequence": 2, "governance_state": "CREATED", "timestamp_ns": ts + 1},
    ]
    cdb = _make_db(rows_c)
    rdb = _make_db(rows_r)

    res = replay_verifier.verify_replay(cdb, rdb)
    assert res.canonical_hash is not None
    assert res.replay_hash is not None
    assert res.canonical_hash != res.replay_hash
