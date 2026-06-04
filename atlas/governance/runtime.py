from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import threading


@dataclass
class GovernanceRuntimeContext:
    """Root governance state for Phase 38.

    Fields are intentionally simple and serializable; this object is
    intended to be held in-memory and passed to governance components.
    """

    strict_mode: bool = True
    governance_mode: str = "enforce"  # 'enforce' or 'shadow'
    violation_mode: str = "enforce"
    quarantine_enabled: bool = True
    trace_policy: str = "strict"
    lineage_policy: str = "strict"
    replay_policy: str = "validate"
    identity_policy: str = "strict"
    metrics: Dict[str, int] = field(default_factory=lambda: {
        "identity_contract_violations": 0,
        "lineage_break_attempts": 0,
        "trace_propagation_failures": 0,
        "rejected_writes": 0,
        "quarantine_events": 0,
        "immutable_context_success_rate": 0,
        "causal_replay_integrity": 0,
        # Phase 38 governance telemetry
        "intercepted_operations": 0,
        "bypass_attempts": 0,
        "rejected_operations": 0,
        "repaired_operations": 0,
        "quarantined_operations": 0,
        "lineage_breaks": 0,
        "trace_propagation_failures": 0,
        "replay_divergence": 0,
        "orphan_mutations": 0,
        "duplicate_identity_attempts": 0,
        "identity_operations_total": 0,
        "identity_operations_governed": 0,
        "identity_operations_bypassed": 0,
    })
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # governance session id for persisted records
    session_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)
    # optional persistence layer (set by engine or wiring)
    persistence: object | None = field(default=None, repr=False)

    # deterministic sequence counter for events within this session
    _sequence_counter: int = field(default=0, repr=False)
    # simple stack to track parent event ids for causal chaining
    _parent_stack: list = field(default_factory=list, repr=False)

    def next_sequence(self) -> int:
        with self._lock:
            self._sequence_counter += 1
            return self._sequence_counter

    def push_parent(self, event_id: str | None) -> None:
        with self._lock:
            self._parent_stack.append(event_id)

    def pop_parent(self) -> None:
        with self._lock:
            if self._parent_stack:
                self._parent_stack.pop()

    def current_parent(self) -> str | None:
        with self._lock:
            if not self._parent_stack:
                return None
            return self._parent_stack[-1]

    def generate_event_identity(self, operation: str, payload: Dict[str, Any], interception_stage: str, parent_event_id: str | None = None) -> Dict[str, Any]:
        """Create a deterministic event identity based on session, sequence, payload, and stage.

        The returned dict contains: event_id, parent_event_id, governance_session_id,
        operation_sequence, interception_stage, operation_hash.
        """
        import json, hashlib, uuid

        exec_context = payload.get("execution_context") if isinstance(payload, dict) else None
        if not isinstance(exec_context, dict):
            exec_context = {}

        seq = self.next_sequence()
        trace_id = str(exec_context.get("trace_id") or self.session_id)
        lineage_id = str(exec_context.get("lineage_id") or trace_id)
        parent = parent_event_id or exec_context.get("parent_id") or self.current_parent()
        # canonical JSON of stable fields
        canonical = json.dumps({
            "session_id": self.session_id,
            "trace_id": trace_id,
            "lineage_id": lineage_id,
            "sequence": seq,
            "parent": parent,
            "operation": operation,
            "stage": interception_stage,
            "payload": payload,
        }, sort_keys=True, separators=(',', ':'))
        op_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        # deterministic UUID5 based on op_hash and session
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, trace_id)
        event_uuid = uuid.uuid5(namespace, op_hash)
        event_id = event_uuid.hex
        # compute causal depth and root id from the parent stack
        with self._lock:
            depth = len(self._parent_stack) + 1
            root = self._parent_stack[0] if self._parent_stack else event_id

        import time

        return {
            "event_id": event_id,
            "trace_id": trace_id,
            "lineage_id": lineage_id,
            "parent_event_id": parent,
            "root_event_id": root,
            "governance_session_id": self.session_id,
            "operation_sequence": seq,
            "interception_stage": interception_stage,
            "causal_depth": depth,
            "operation_hash": op_hash,
            "replay_epoch": 0,
            "timestamp_ns": time.time_ns(),
        }
    def increment_metric(self, name: str, amount: int = 1) -> None:
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = 0
            self.metrics[name] += amount

    def get_metrics_snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self.metrics)
