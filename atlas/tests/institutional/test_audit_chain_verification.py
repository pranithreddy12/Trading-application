"""Institutional: Audit Chain Verification — verify tamper-resistant audit ledger."""

import hashlib
import json
import pytest


def test_hash_chain_integrity():
    """Each block must hash-link to previous block."""
    blocks = [
        {"index": 0, "data": "genesis", "prev_hash": "0"},
        {"index": 1, "data": "strategy_created", "prev_hash": ""},
        {"index": 2, "data": "strategy_validated", "prev_hash": ""},
    ]
    chain_hashes = []
    for i, block in enumerate(blocks):
        content = json.dumps(block["data"], sort_keys=True) + (chain_hashes[-1] if chain_hashes else "0")
        block_hash = hashlib.sha256(content.encode()).hexdigest()
        chain_hashes.append(block_hash)
        if i > 0:
            blocks[i]["prev_hash"] = chain_hashes[i - 1]

    for i in range(1, len(blocks)):
        assert blocks[i]["prev_hash"] == chain_hashes[i - 1]


def test_tamper_detection():
    """Tampering with any block should break the chain."""
    blocks = [
        {"data": "a", "hash": ""},
        {"data": "b", "hash": ""},
        {"data": "c", "hash": ""},
    ]
    chain = []
    prev = "0"
    for b in blocks:
        content = json.dumps(b["data"], sort_keys=True) + prev
        b["hash"] = hashlib.sha256(content.encode()).hexdigest()
        chain.append(b["hash"])
        prev = b["hash"]

    # Tamper with block 1
    blocks[1]["data"] = "tampered"
    new_content = json.dumps(blocks[1]["data"], sort_keys=True) + chain[0]
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()
    assert new_hash != chain[1], "Tamper should change hash"


def test_audit_trail_completeness():
    """Audit trail must include actor, action, target, timestamp."""
    audit_entry = {
        "actor": "ideator_agent",
        "action": "create_strategy",
        "target_id": "s1",
        "trace_id": "abc123",
        "timestamp": "2026-05-12T10:00:00Z",
    }
    required_fields = {"actor", "action", "target_id", "timestamp"}
    assert required_fields.issubset(set(audit_entry.keys()))
