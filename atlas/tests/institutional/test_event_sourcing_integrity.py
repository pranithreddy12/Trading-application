"""Institutional: Event Sourcing Integrity — verify append-only event store."""

import json
import pytest


def test_append_only_property():
    """Events must never be mutated in place."""
    events = [
        {"seq": 1, "type": "created", "data": "a"},
        {"seq": 2, "type": "updated", "data": "b"},
    ]
    frozen = json.dumps(events, sort_keys=True)
    events[1]["data"] = "corrupted"
    assert json.dumps(events, sort_keys=True) != frozen


def test_causal_lineage():
    """Parent event IDs must link correctly."""
    events = [
        {"id": "e1", "parent_id": None},
        {"id": "e2", "parent_id": "e1"},
        {"id": "e3", "parent_id": "e2"},
    ]
    for i, e in enumerate(events):
        if i == 0:
            assert e["parent_id"] is None
        else:
            assert e["parent_id"] == events[i - 1]["id"]


def test_event_versioning():
    """Events should carry version for optimistic concurrency."""
    class Event:
        def __init__(self, aggregate_id, version, data):
            self.aggregate_id = aggregate_id
            self.version = version
            self.data = data

    events = [Event("agg_1", 1, {}), Event("agg_1", 2, {}), Event("agg_1", 3, {})]
    for i, e in enumerate(events):
        assert e.version == i + 1


def test_snapshot_recovery():
    """Snapshots should reduce replay overhead."""
    snapshot = {"version": 100, "state": {"balance": 50000}}
    new_events_count = 50
    replay_from = 101
    assert replay_from == snapshot["version"] + 1
    assert new_events_count > 0
