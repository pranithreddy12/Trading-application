# ATLAS — End-to-End Execution Flow

The ATLAS ecosystem operates as a **continuous autonomous circulation loop** from raw market data to strategy evolution.

---

## Complete Circulation Path

```
Market Data (L1)
    │
    ▼
Scout Network (L7) ───► Hypothesis Formation ───► Ideation (L2)
    │                                                   │
    │                                                   ▼
    │                                            Mutation (L2)
    │                                                   │
    │                                                   ▼
    │                                            Code Generation (L2)
    │                                                   │
    │                                                   ▼
    │                                      Backtesting (L3)
    │                                           │
    │                                           ▼
    │                                      Validation (L3)
    │                                           │
    │                                   ┌───────┴───────┐
    │                                   ▼               ▼
    │                              Portfolio        Rejected
    │                              Intelligence (L4)
    │                                   │
    │                                   ▼
    │                              Capital Allocation (L4)
    │                                   │
    │                                   ▼
    │                              Execution (L5)
    │                                   │
    │                                   ▼
    │                              Event Store (L6)
    │                                   │
    │                                   ▼
    │                              Audit Ledger (L6)
    │                                   │
    │                                   ▼
    │                    ┌──────────────┴──────────────┐
    │                    ▼                             ▼
    │           Economic Efficiency (L7)      Replay Verification (L6)
    │                    │                             │
    │                    ▼                             ▼
    │           Attribution (L7)            Replay Integrity Score
    │                    │
    │                    ▼
    │           Retirement / Survival (L7)
    │                    │
    └────────────────────┘
         (loop continues)
```

---

## Key Flow Stages

### 1. Ingestion → Features
- Market data streams via WebSocket/REST (L1)
- Features computed (technical indicators, patterns)
- Data persisted to TimescaleDB hypertables

### 2. Scouts → Hypothesis
- 12+ scouts collect information (regime, liquidity, sentiment, news)
- Scout signals feed hypothesis engine
- High-confidence hypotheses trigger ideation

### 3. Ideation → Strategy
- Ideator generates strategy concepts conditioned on scout signals
- Mutator creates variations of existing strategies
- CoderAgent generates executable strategy code
- Strategies scored by composite fitness

### 4. Backtest → Validation
- Historical backtesting with realistic costs
- Walk-forward analysis for temporal consistency
- Monte Carlo simulation for probabilistic assessment
- Overfitting detection for parameter stability
- Composite fitness score computed (Sharpe, Sortino, Calmar, expectancy)

### 5. Portfolio → Risk
- Portfolio intelligence assesses concentration/diversification
- Capital allocator distributes funds via Kelly/risk-parity
- Systemic risk engine monitors contagion risk
- Stress tests simulate crisis scenarios

### 6. Execution → Trading
- Execution gateway routes orders with fill simulation
- Copy trader replicates leader signals to followers
- Execution realism models slippage/latency/degradation
- Dead-letter queue captures and classifies failures
- Recovery manager reconciles on restart

### 7. Event Store → Audit
- Each lifecycle event persisted immutably
- Audit ledger maintains per-trace_id sequence chain
- Replay engine verifies hash-chain integrity
- All events replayable for forensic analysis

### 8. Attribution → Evolution
- Economic attribution credits scout signals for P&L impact
- Dominant organisms identified and boosted
- Underperformers retired and penalized
- Mutation lineage tracks evolutionary success
- Regime specialization profiles emerge
