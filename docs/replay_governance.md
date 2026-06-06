# ATLAS — Replay & Governance

ATLAS provides **institutional-grade** event sourcing, audit, and replay integrity for full operational transparency.

---

## Event Store

The **EventStore** is an immutable, append-only log that captures every state-changing event.

| Property | Implementation |
|----------|---------------|
| **Immutability** | Append-only — no updates or deletes |
| **Hash chain** | Each event references previous hash for tamper detection |
| **Aggregate streams** | Events grouped by aggregate_type + aggregate_id |
| **Versioning** | Strictly incrementing sequence per aggregate |

```
Event N-1                    Event N                     Event N+1
┌──────────────┐            ┌──────────────┐            ┌──────────────┐
│ event_id     │            │ event_id     │            │ event_id     │
│ aggregate_id │──────────► │ aggregate_id │──────────► │ aggregate_id │
│ prev_hash    │            │ prev_hash    │            │ prev_hash    │
│ hash         │            │ hash         │            │ hash         │
│ created_at   │            │ created_at   │            │ created_at   │
│ payload      │            │ payload      │            │ payload      │
└──────────────┘            └──────────────┘            └──────────────┘
```

---

## Audit Ledger

The **AuditLedger** provides a per-trace_id sequence-gated audit trail.

| Feature | Description |
|---------|-------------|
| **Sequence gating** | Each trace_id has auto-incrementing sequence numbers |
| **Event types** | validation, mutation, deployment, retirement, risk, system |
| **Actor tracking** | Every entry records the originating agent |
| **Resource linking** | References strategy_id, trace_id for full traceability |

---

## Replay Engine

The **ReplayEngine** performs deterministic replay to verify data integrity.

### Integrity Verification

1. **Fetch** all events for an aggregate stream
2. **Recompute** hash chain deterministically
3. **Compare** computed hashes against stored hashes
4. **Report** violations with aggregate_id + event_id

### Integrity Score Formula

```
integrity_score = (1 - violations / total_events) × 100
```

A score of **100** means perfect replay integrity — zero hash chain violations.

---

## Governance Components

| Component | Function |
|-----------|----------|
| **DeploymentGovernor** | Approval workflow for strategy deployment |
| **LeaderGovernanceEngine** | Copy trading leader qualification |
| **KillSwitch** | Emergency halt of all trading |
| **SystemHealthEngine** | Composite system health scoring |
| **AgentPerformanceGovernor** | Agent reliability monitoring |

---

## Immutability Guarantees

- ✅ **Event store**: Append-only, hash-chained
- ✅ **Audit ledger**: Sequence-gated, append-only
- ✅ **Replay integrity**: Deterministic verification
- ✅ **Failed inserts**: Dead-letter queue preserves failed writes
- ✅ **Canonical UUIDs**: All IDs use deterministic UUID generation
