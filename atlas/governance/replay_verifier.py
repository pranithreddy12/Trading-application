from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import sqlite3

from atlas.governance import state
from atlas.governance import hashing


@dataclass
class ReplayVerificationResult:
    hash_match: bool
    sequence_match: bool
    state_transition_match: bool
    divergence_reason: Optional[str]
    divergence_event_id: Optional[str]
    divergence_index: Optional[int]
    canonical_hash: Optional[str] = None
    replay_hash: Optional[str] = None
    divergence_hash: Optional[str] = None
    event_hashes_canonical: Optional[List[str]] = None
    event_hashes_replay: Optional[List[str]] = None
    illegal_transition_detected: bool = False
    illegal_in_canonical: bool = False
    illegal_in_replay: bool = False
    illegal_event_id: Optional[str] = None
    illegal_index: Optional[int] = None


def _get_conn(db: Union[str, sqlite3.Connection]):
    if isinstance(db, sqlite3.Connection):
        return db
    return sqlite3.connect(db)


def _load_events(conn: sqlite3.Connection) -> List[Dict]:
    cur = conn.cursor()
    cur.execute("SELECT event_id, operation_hash, operation_sequence, governance_state, timestamp_ns FROM governance_operation_log ORDER BY timestamp_ns, operation_sequence")
    rows = cur.fetchall()
    return [dict(event_id=r[0], operation_hash=r[1], operation_sequence=r[2], governance_state=r[3], timestamp_ns=r[4]) for r in rows]


def verify_replay(canonical_db: Union[str, sqlite3.Connection], replay_db: Union[str, sqlite3.Connection]) -> ReplayVerificationResult:
    cconn = _get_conn(canonical_db)
    rconn = _get_conn(replay_db)

    canonical = _load_events(cconn)
    replay = _load_events(rconn)

    # Compute per-event event_hashes and stream hashes (deterministic canonicalization)
    canonical_stream_hash, canonical_hashes = hashing.compute_stream_hash(canonical)
    replay_stream_hash, replay_hashes = hashing.compute_stream_hash(replay)

    # Index replay by event_id for quick lookup
    replay_index = {e['event_id']: e for e in replay}

    hash_ok = True
    seq_ok = True
    state_ok = True
    divergence_reason = None
    divergence_event_id = None
    divergence_index = None

    for idx, ce in enumerate(canonical):
        eid = ce['event_id']
        re = replay_index.get(eid)
        if re is None:
            divergence_reason = 'missing_event'
            divergence_event_id = eid
            divergence_index = idx
            hash_ok = False
            seq_ok = False
            state_ok = False
            break

        if (ce.get('operation_hash') or '') != (re.get('operation_hash') or ''):
            divergence_reason = 'hash_mismatch'
            divergence_event_id = eid
            divergence_index = idx
            hash_ok = False
            break

        if (ce.get('operation_sequence') or 0) != (re.get('operation_sequence') or 0):
            divergence_reason = 'sequence_mismatch'
            divergence_event_id = eid
            divergence_index = idx
            seq_ok = False
            break

        if (ce.get('governance_state') or '') != (re.get('governance_state') or ''):
            divergence_reason = 'state_transition_mismatch'
            divergence_event_id = eid
            divergence_index = idx
            state_ok = False
            break

    # Scan for illegal transitions inside canonical and replay runs
    def _scan_illegal(conn):
        rows = _load_events(conn)
        last_by_event = {}
        for idx, r in enumerate(rows):
            eid = r.get('event_id')
            state_val = r.get('governance_state')
            if not state_val:
                continue
            try:
                new_state = state.GovernanceEventState(state_val)
            except Exception:
                continue
            prev = last_by_event.get(eid)
            try:
                state.validate_transition(prev, new_state)
            except state.InvalidGovernanceTransition:
                return True, eid, idx
            last_by_event[eid] = new_state
        return False, None, None

    illegal_c, ieid_c, iidx_c = _scan_illegal(cconn)
    illegal_r, ieid_r, iidx_r = _scan_illegal(rconn)
    divergence_hash = hashing.compute_divergence_hash(canonical_hashes, divergence_index)

    return ReplayVerificationResult(
        hash_match=hash_ok,
        sequence_match=seq_ok,
        state_transition_match=state_ok,
        divergence_reason=divergence_reason,
        divergence_event_id=divergence_event_id,
        divergence_index=divergence_index,
        canonical_hash=canonical_stream_hash,
        replay_hash=replay_stream_hash,
        divergence_hash=divergence_hash,
        event_hashes_canonical=canonical_hashes,
        event_hashes_replay=replay_hashes,
        illegal_transition_detected=(illegal_c or illegal_r),
        illegal_in_canonical=illegal_c,
        illegal_in_replay=illegal_r,
        illegal_event_id=ieid_c or ieid_r,
        illegal_index=iidx_c or iidx_r,
    )
