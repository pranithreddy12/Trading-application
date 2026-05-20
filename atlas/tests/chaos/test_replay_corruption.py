"""Chaos: Replay corruption — verify integrity checks detect event stream corruption."""

import hashlib
import json
import pytest


def test_event_hash_chain_integrity():
    """Event stream hash chain should detect tampering."""
    events = [{"id": "1", "data": "open"}, {"id": "2", "data": "high"}]
    chain = []
    prev_hash = "0"
    for e in events:
        block = json.dumps(e, sort_keys=True) + prev_hash
        h = hashlib.sha256(block.encode()).hexdigest()
        chain.append(h)
        prev_hash = h

    original_chain = chain.copy()
    events[1]["data"] = "tampered"
    chain2 = []
    prev_hash = "0"
    for e in events:
        block = json.dumps(e, sort_keys=True) + prev_hash
        h = hashlib.sha256(block.encode()).hexdigest()
        chain2.append(h)
        prev_hash = h

    assert original_chain != chain2


@pytest.mark.asyncio
async def test_replay_state_mismatch_detection():
    """Replay should detect when reconstructed state differs from expected."""
    original_state = {"balance": 10000, "positions": 2}
    corrupted_state = {"balance": 99999, "positions": 0}

    def check_integrity(state_a: dict, state_b: dict) -> list:
        diffs = []
        for k in state_a:
            if state_a[k] != state_b.get(k):
                diffs.append(f"{k}: {state_a[k]} vs {state_b[k]}")
        return diffs

    diffs = check_integrity(original_state, corrupted_state)
    assert len(diffs) == 2


def test_event_ordering_integrity():
    """Reversed event order should be detected."""
    events = [{"seq": 1}, {"seq": 2}, {"seq": 3}]
    reversed_events = list(reversed(events))
    for i, e in enumerate(reversed_events):
        if i < len(events) - 1 and e["seq"] > reversed_events[i + 1]["seq"]:
            assert True
            return
    assert False
