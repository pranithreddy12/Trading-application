from atlas.governance.runtime import GovernanceRuntimeContext


def test_replay_determinism_simple_sequence():
    # fixed session id to ensure deterministic namespace
    sid = "00000000-0000-4000-8000-000000000000"
    r1 = GovernanceRuntimeContext()
    r2 = GovernanceRuntimeContext()
    r1.session_id = sid
    r2.session_id = sid
    # ensure counters start at same place
    r1._sequence_counter = 0
    r2._sequence_counter = 0

    ops = [
        ("op_a", {"x": 1}),
        ("op_b", {"y": 2}),
        ("op_c", {"z": 3}),
    ]

    ids1 = []
    ids2 = []
    for op, payload in ops:
        em1 = r1.generate_event_identity(op, payload, interception_stage="pre")
        em2 = r2.generate_event_identity(op, payload, interception_stage="pre")
        ids1.append((em1["event_id"], em1["operation_hash"]))
        ids2.append((em2["event_id"], em2["operation_hash"]))

    assert ids1 == ids2


def test_replay_determinism_with_parent_stack():
    sid = "11111111-1111-4111-8111-111111111111"
    r1 = GovernanceRuntimeContext()
    r2 = GovernanceRuntimeContext()
    r1.session_id = sid
    r2.session_id = sid
    r1._sequence_counter = 0
    r2._sequence_counter = 0

    # simulate parent-child relationships
    parent1 = r1.generate_event_identity("root", {"a": 1}, interception_stage="pre")
    parent2 = r2.generate_event_identity("root", {"a": 1}, interception_stage="pre")
    assert parent1["event_id"] == parent2["event_id"]

    # push parent to stack to simulate nested operations
    r1.push_parent(parent1["event_id"])
    r2.push_parent(parent2["event_id"])

    child1 = r1.generate_event_identity("child", {"b": 2}, interception_stage="post")
    child2 = r2.generate_event_identity("child", {"b": 2}, interception_stage="post")

    assert child1["event_id"] == child2["event_id"]
    assert child1["root_event_id"] == child2["root_event_id"]
    assert child1["causal_depth"] == child2["causal_depth"]
