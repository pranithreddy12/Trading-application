# ATLAS — Architecture Overview

ATLAS is an **autonomous adaptive trading ecosystem** built on a 7-layer agent architecture with institutional-grade governance, replay, audit, and evolutionary intelligence.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    L7 — META-LEARNING                     │
│  Scouts · Synthesis · Specialization · Evolution         │
├─────────────────────────────────────────────────────────┤
│                    L6 — GOVERNANCE                        │
│  Event Store · Audit Ledger · Replay · Kill Switch       │
├─────────────────────────────────────────────────────────┤
│                    L5 — EXECUTION                         │
│  Gateway · Copy Trading · Dead-Letter · Realism          │
├─────────────────────────────────────────────────────────┤
│                    L4 — RISK & CAPITAL                    │
│  Portfolio · Allocator · Systemic Risk · Stress Tests    │
├─────────────────────────────────────────────────────────┤
│                    L3 — BACKTESTING                       │
│  Runner · Validator · Walk-Forward · Monte Carlo         │
├─────────────────────────────────────────────────────────┤
│                    L2 — STRATEGY                          │
│  Ideator · Mutator · Coder · Combiner                    │
├─────────────────────────────────────────────────────────┤
│                    L1 — DATA                              │
│  REST/WS Ingestion · Features · Patterns                 │
└─────────────────────────────────────────────────────────┘
```

---

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Deterministic** | All mutations, replay, and governance use canonical UUIDs |
| **Immutable** | Event store, audit ledger — append-only |
| **Evolutionary** | Strategies mutate, compete, and are selected by fitness |
| **Self-governing** | Health checks, kill switches, performance governors |
| **Scout-driven** | 12+ intelligence scouts feed meta-learning layer |

---

## Key Components

| Component | Role |
|-----------|------|
| **Event Store** | Immutable append-only log with hash-chained integrity |
| **Audit Ledger** | Per-trace_id sequence-gated audit trail |
| **Replay Engine** | Deterministic replay with integrity verification |
| **Mutation Engine** | Evolutionary strategy variation with lineage tracking |
| **Scout Network** | 12+ information sources (regime, liquidity, news, sentiment) |
| **Portfolio Intelligence** | Adaptive capital allocation with regime conditioning |
| **Execution Realism** | Simulated fill/slippage/latency modeling |
| **Dead-Letter Recovery** | Classification + replay for failed orders |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11+ asyncio |
| Database | TimescaleDB (PostgreSQL + hypertables) |
| Cache/Messaging | Redis |
| API | FastAPI |
| Orchestration | MetaOrchestrator |
| Monitoring | psutil + event loop telemetry |
