import sqlite3
from atlas.governance.persistence import GovernancePersistenceLayer
from atlas.governance.replay_verifier import ReplayVerificationResult
import tempfile
import os


def test_persist_replay_verification_creates_row():
    # use a temporary file for sqlite
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        g = GovernancePersistenceLayer(db_url=f'sqlite:///{path}')
        res = ReplayVerificationResult(hash_match=False, sequence_match=False, state_transition_match=False, divergence_reason='hash_mismatch', divergence_event_id='E1', divergence_index=10, illegal_transition_detected=False)
        g.persist_replay_verification(replay_id='r1', canonical_session_id='c1', replay_session_id='r1', root_event_id='root', verification_state='DIVERGED', divergence_event_id='E1', escalation_decision='QUARANTINE', illegal_transition_count=0, canonical_hash='ch', replay_hash='rh', causal_depth=3, replay_epoch=1, created_at_ns=123456)
        # verify row exists
        import sqlite3
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT replay_id, verification_state, divergence_event_id FROM governance_replay_verification_log")
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 'r1'
        assert rows[0][1] == 'DIVERGED'
        assert rows[0][2] == 'E1'
        conn.close()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
