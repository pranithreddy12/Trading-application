from __future__ import annotations

import json
import hashlib
from typing import Dict, List, Any


def canonicalize_event_for_hash(event: Dict[str, Any]) -> Dict[str, Any]:
    # Select deterministic subset of fields suitable for long-term hashing
    keys = [
        "event_id",
        "parent_event_id",
        "root_event_id",
        "event_state",
        "operation",
        "decision",
        "trace_id",
        "strategy_id",
        "operation_sequence",
    ]
    out = {}
    for k in keys:
        # normalize missing values to None
        out[k] = event.get(k) if k in event else None
    return out


def json_deterministic_dump(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(event: Dict[str, Any]) -> str:
    canon = canonicalize_event_for_hash(event)
    s = json_deterministic_dump(canon)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def stream_hash_from_event_hashes(hashes: List[str]) -> str:
    # Combine ordered event hashes deterministically
    m = hashlib.sha256()
    for h in hashes:
        # use newline separator to avoid ambiguity
        m.update(h.encode("utf-8"))
        m.update(b"\n")
    return m.hexdigest()


def compute_stream_hash(events: List[Dict[str, Any]]) -> (str, List[str]):
    hashes = [event_hash(e) for e in events]
    return stream_hash_from_event_hashes(hashes), hashes


def compute_divergence_hash(hashes: List[str], divergence_index: int | None) -> str | None:
    if divergence_index is None:
        return None
    # Hash up to and including divergence index
    prefix = hashes[: divergence_index + 1]
    return stream_hash_from_event_hashes(prefix)
