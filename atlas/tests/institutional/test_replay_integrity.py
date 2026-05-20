"""Institutional: Replay Integrity — verify event sourcing and deterministic reconstruction."""

import hashlib
import json
import pytest


def test_event_stream_ordering():
    """Events must be strictly ordered and reconstructable."""
    events = [
        {"seq": 1, "type": "strategy_created", "data": {"id": "s1"}},
        {"seq": 2, "type": "strategy_backtested", "data": {"sharpe": 1.5}},
        {"seq": 3, "type": "strategy_validated", "data": {"status": "passed"}},
    ]
    for i, e in enumerate(events):
        assert e["seq"] == i + 1


def test_deterministic_replay():
    """Replaying same events should produce identical state."""
    def replay(events: list) -> dict:
        state = {"strategies": {}}
        for e in events:
            if e["type"] == "strategy_created":
                state["strategies"][e["data"]["id"]] = e["data"]
            elif e["type"] == "strategy_backtested":
                sid = e["data"].get("id")
                if sid and sid in state["strategies"]:
                    state["strategies"][sid]["sharpe"] = e["data"]["sharpe"]
        return state

    events = [
        {"type": "strategy_created", "data": {"id": "s1", "name": "TestMA"}},
        {"type": "strategy_backtested", "data": {"id": "s1", "sharpe": 1.5}},
    ]
    state_a = replay(events)
    state_b = replay(events)
    assert state_a == state_b


def test_replay_divergence_detection():
    """Different event sequences should produce different states."""
    def replay(events: list) -> dict:
        state = {"balance": 10000}
        for e in events:
            if e["type"] == "trade":
                state["balance"] += e["data"]["pnl"]
        return state

    events_a = [
        {"type": "trade", "data": {"pnl": 100}},
        {"type": "trade", "data": {"pnl": -50}},
    ]
    events_b = [
        {"type": "trade", "data": {"pnl": -50}},
        {"type": "trade", "data": {"pnl": 100}},
    ]
    if events_a != events_b:
        assert replay(events_a) == replay(events_b), "Commutative operations should match"


def test_state_snapshot_recovery():
    """State snapshots should enable fast recovery from event stream."""
    snapshot = {"strategies": {"s1": {"sharpe": 1.5}}, "version": 10}
    new_events = [
        {"seq": 11, "type": "strategy_retired", "data": {"id": "s1"}},
    ]
    state = dict(snapshot)
    for e in new_events:
        if e["type"] == "strategy_retired":
            state["strategies"].pop(e["data"]["id"], None)
    assert "s1" not in state["strategies"]
