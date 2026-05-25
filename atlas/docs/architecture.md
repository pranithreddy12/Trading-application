# ATLAS Architecture Overview

**Version:** 1.0.0  
**Classification:** Institutional-Grade Autonomous Trading System  
**Updated:** May 2026

---

## 1. System Philosophy

ATLAS is an **autonomous strategy evolution platform** — not a fixed trading bot. Strategies are generated, backtested, validated, mutated, and retired in a continuous lifecycle. The system uses a **7-layer agent hierarchy** with emergent intelligence at the meta layer, scout networks for external signal ingestion, and a fully observable control plane for operator oversight.

```
┌──────────────────────────────────────────────────────────────┐
│                     OPERATOR / CLIENT                         │
│          (Dashboard UI · API · Control Plane)                 │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│  L7 ─── META INTELLIGENCE LAYER                              │
│  • MetaReasoningAgent    • MutationPolicyEngine               │
│  • FailureAnalysisEngine • FeatureEvolutionEngine             │
│  • HypothesisEngine      • ScoutSynthesisEngine               │
│  • SystemHealthEngine    • AntiPoisoningEngine                │
│  • StrategyRetirementEngine                                   │
├──────────────────────────────────────────────────────────────┤
│  L6 ─── PORTFOLIO LAYER                                       │
│  • PortfolioIntelligenceEngine                                │
├──────────────────────────────────────────────────────────────┤
│  L5 ─── EXECUTION LAYER                                       │
│  • ExecutionGateway      • OrderTracker                       │
│  • KillSwitch            • CopyTraderService                  │
├──────────────────────────────────────────────────────────────┤
│  L4 ─── RISK LAYER                                            │
│  • RiskController        • SystemicRiskAssessor               │
│  • CapitalPreservation   • StressTestEngine                   │
├──────────────────────────────────────────────────────────────┤
│  L3 ─── VALIDATION LAYER                                      │
│  • BacktestRunner        • ValidatorAgent                     │
│  • RegimeValidator       • ShortWindowEvaluator               │
│  • WalkForwardAnalysis   • MonteCarloAnalysis                 │
│  • OverfittingAnalysis   • CostStressAnalysis                 │
├──────────────────────────────────────────────────────────────┤
│  L2 ─── STRATEGY LAYER                                        │
│  • IdeatorAgentV2        • CoderAgent                         │
│  • StrategyNormalizer    • StrategyGrammar                    │
├──────────────────────────────────────────────────────────────┤
│  L1 ─── SCOUT NETWORK · DATA INGESTION                        │
│  • HypothesisValidationEngine                                 │
│  • NewsIntelligenceEngine                                     │
│  • SourceReliabilityEngine                                    │
│  • ExternalScoutMemory                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Core Infrastructure

### 2.1 Communication Layer

All agents communicate via **Redis pub/sub channels** through a centralized `MessagingClient`:

```
Agent → MessagingClient.publish(channel, message)
Agent → MessagingClient.subscribe(channel, callback)
```

The `BaseAgent` abstract class provides lifecycle management:

```python
class BaseAgent(ABC):
    def __init__(self, name, agent_type, layer, redis_client, advisory_only=False):
        self.agent_id = str(uuid.uuid4())
        self.messaging = MessagingClient(...)
        self.db_client = TimescaleClient(...)
```

### 2.2 Meta-Orchestrator

The `MetaOrchestrator` coordinates the full pipeline as a directed acyclic graph:

```
IdeatorAgent → CoderAgent → BacktestRunner → ValidatorAgent
                                                      │
                                           (passed?)  │
                                                      ▼
                                              PortfolioIntelligenceEngine
                                                      │
                                                      ▼
                                              ExecutionGateway
```

### 2.3 Event Lineage

Every action is traced via a `TraceContext` through `EventLineage`, providing full causal chain reconstruction for audit and replay.

---

## 3. Core Packages

### 3.1 `atlas/core/` — System Foundation

| Module | Responsibility |
|---|---|
| `agent_base.py` | Abstract base class with lifecycle hooks, heartbeat, and messaging integration |
| `meta_orchestrator.py` | Pipeline orchestration — DAG execution of the strategy lifecycle |
| `messaging.py` | Redis pub/sub wrapper with typed message support |
| `claude_client.py` | LLM integration (Claude API) for strategy generation and analysis |
| `score_contract.py` | Standardized strategy scoring schema |
| `execution_cost_intelligence.py` | Dynamic cost governance — edge-per-trade thresholds |
| `event_lineage.py` | Causal tracing system with full replay capability |

### 3.2 `atlas/config/` — System Configuration

`settings.py` centralizes all system configuration:

```python
class Settings:
    database_url: str        # TimescaleDB connection
    redis_url: str           # Redis pub/sub + state
    environment: str         # dev / staging / production
    log_level: str
    max_strategies_per_cycle: int
    claude_api_key: str
    alpaca_api_key: str
    scout_api_keys: dict
```

Environment is loaded from `.env` with sensible defaults for development.

### 3.3 `atlas/data/storage/` — Persistence Layer

`TimescaleClient` provides a unified async interface to **TimescaleDB**, a PostgreSQL extension optimized for time-series data. It manages:

- Strategy lifecycle (create → backtest → validate → deploy → retire)
- Backtest results and performance metrics
- Execution logs and paper trades
- Portfolio intelligence snapshots
- Scout signal memory
- Event store and audit ledger
- Anomaly observations

The schema uses `JSONB` extensively for flexible metric storage across agents.

---

## 4. Agent Layer Details

### 4.1 L1 — Scout Network

The scout network ingests external signals from news, social media, sentiment feeds, and market data providers. Scouts run continuously and feed intelligence to all higher layers:

```
ExternalScoutMemory (TimescaleDB)
    ↑
ScoutSynthesisEngine (L7) → Consensus scoring → Strategy Ideation
    ↑
NewsIntelligenceEngine      HypothesisValidationEngine
    ↑                                ↑
SourceReliabilityEngine      SourceReliabilityEngine
```

**Key architecture:** Scouts are NOT simple data fetchers. They analyze source reliability over time, maintain dynamic trust scores, and contribute to a consensus synthesis that modulates strategy generation.

### 4.2 L2 — Strategy Layer

**IdeatorAgentV2** generates strategy specifications using LLM prompts enriched with:

- Current market regime (from scouts)
- Recent strategy performance (from database)
- Diversity governance (anti-collapse)
- Economic constraints (trade frequency / edge-per-trade)
- Ecological pressure (adaptive generation rate)
- Pattern intelligence (from L7 meta-reasoning)

**CoderAgent** converts each specification into executable Python code using a **strategy grammar** with 4 architecture types (momentum, mean_reversion, breakout, volatility) and validated regime classification.

### 4.3 L3 — Validation Layer

Three-stage validation pipeline:

1. **BacktestRunner** — Minutely OHLCV backtest with dynamic slippage and commission modeling
2. **ValidatorAgent** — Institutional rules engine:
   - Sharpe ratio ≥ 1.0 (production) / 0.5 (dev)
   - Maximum drawdown ≤ 25%
   - Minimum 30 trades
   - Profit factor ≥ 1.2
   - Walk-forward analysis (holdout vs train consistency)
   - Overfitting detection
   - Cost governance (edge-per-trade minimum)  
   - Monte Carlo survival
3. **RegimeValidator** — Validates strategy survives multiple market regimes

### 4.4 L4 — Risk Layer

Multi-layered risk governance:

```
KillSwitch (emergency stop) → Systemic Risk Assessment
    ↑                                    ↑
CapitalPreservation ─── StressTestEngine
```

- **KillSwitch** — Emergency halt across all execution
- **SystemicRisk** — Measures portfolio fragility, contagion probability, correlation regime
- **CapitalPreservation** — Drawdown-based capital reduction
- **StressTest** — Scenario-based portfolio survival simulation

### 4.5 L5 — Execution Layer

**ExecutionGateway** manages all paper/copy trade execution:

- Dynamic position sizing
- Order deduplication
- Dead letter queue for failed orders
- Execution realism simulation (slippage, fill probability, latency)
- Copy trading with leader/follower accounts

### 4.6 L6 — Portfolio Layer

**PortfolioIntelligenceEngine** computes:

- Diversification across strategies
- Concentration risk
- Ensemble survivability
- Capital allocation (weighted by sharpe, win rate, drawdown)
- Drift detection (feature, strategy, regime)

### 4.7 L7 — Meta Intelligence Layer

The most architecturally complex layer — **agents that govern agents**:

| Engine | Function |
|---|---|
| **MetaReasoningAgent** | System-wide advisories based on cross-layer trends |
| **MutationPolicyEngine** | Controls exploration vs exploitation — when to mutate vs when to generate |
| **FailureAnalysisEngine** | Root cause analysis of strategy/execution failures |
| **FeatureEvolutionEngine** | Tracks which features survive and which decay |
| **HypothesisEngine** | Maintains a registry of beliefs with evidence/contradiction tracking |
| **ScoutSynthesisEngine** | Consensus scoring across scout signals |
| **SystemHealthEngine** | Composite system health score with degraded subsystem detection |
| **AntiPoisoningEngine** | Detects and filters adversarial scout signals |
| **StrategyRetirementEngine** | Retires underperforming or drifted strategies |

---

## 5. API & Control Plane

### 5.1 REST API (FastAPI)

| Endpoint | Description |
|---|---|
| `/health` | System health + component status |
| `/strategies` | Strategy CRUD with status filtering |
| `/portfolio` | Aggregate portfolio value, PnL, drawdown |
| `/positions` | Open position list |
| `/risk` | Kill switch state, drawdown, risk limits |
| `/paper_trades` | Trade log |
| `/leaders` | Copy trading leader accounts |
| `/followers` | Copy trading follower accounts |
| `/copy/logs` | Copy execution logs |
| `/copy/status` | Copy trading system status |
| `/system/logs` | System event log |
| `/kill_switch/activate|deactivate` | Emergency stop |
| `/ws/live` | Real-time WebSocket event stream |

### 5.2 Dashboard (HTML + REST)

The operator dashboard serves a single-page HTML interface with API-driven data:

- **Overview** — System health, strategy counts, backtest volume, pipeline stats
- **Pipeline** — Strategy lifecycle funnel with per-stage counts
- **Traces** — Recent lifecycle events with causal chain visualization
- **Patterns** — Pattern intelligence with confidence scoring
- **Risk** — Kill switch state, copy trader metrics, open positions, PnL
- **Portfolio** — Allocation, diversification, ensemble trades
- **Monitoring** — Drift detection, strategy retirement, execution realism
- **Scouts** — External signal sources with sentiment breakdown
- **Validation** — Walk-forward, Monte Carlo, overfitting, cost stress scores

### 5.3 Control Plane

Operator management endpoints for operational control:

| Endpoint | Description |
|---|---|
| `POST /control/pause-agent` | Pause a running agent |
| `POST /control/resume-agent` | Resume a paused agent |
| `POST /control/restart-agent` | Signal agent restart |
| `POST /control/freeze-capital` | Freeze all capital deployment |
| `POST /control/release-capital` | Release capital freeze |
| `POST /control/retire-strategy` | Force-retire a strategy |
| `GET /control/agent-status` | All agent states from Redis |
| `POST /control/emergency-mode` | Trigger emergency stop |

### 5.4 System Visualization

Graph-structured endpoints for visual analytics:

- **Trace graph** — Causal chains from lifecycle events
- **Mutation lineage** — Parent-child relationships between strategies
- **Portfolio exposure** — Capital allocation map
- **Systemic risk** — Risk assessment visualization
- **Scout influence** — Signal distribution over time
- **Replay timeline** — Event store replay chronology

---

## 6. Observability

### 6.1 Monitoring Fabric

`MonitoringFabric` collects distributed metrics across all subsystems:

- **Counters** — Event throughput (execution, scout, mutation, replay)
- **Latencies** — Execution latency with P50/P95/P99 tracking
- **Flush loop** — 60-second periodic persistence to TimescaleDB
- **Redis real-time** — Live metrics via Redis hashes

### 6.2 Anomaly Monitor

`AnomalyMonitor` runs continuous checks for abnormal patterns:

- Strategy generation spikes
- Execution failure rate > 30%
- Scout signal floods (> 100/hour from a single source)
- Drift escalation (composite severity > 0.8)
- Retirement clustering (> 10/hour)

---

## 7. Observability & Governance

### 7.1 Event Store

Every state transition is recorded in the `event_store` table with:
- `aggregate_type` / `aggregate_id` — Object identity
- `event_type` — State transition name
- `trace_id` — Causal chain linkage
- `parent_event_id` — Parent for replay lineage

### 7.2 Audit Ledger

`audit_ledger` tracks all operator and agent actions:
- `actor` — Who performed the action
- `action` — What was done
- `target_id` — What was affected
- `trace_id` — Cross-reference with event store

### 7.3 Replay Integrity

`replay_integrity` checks verify that event replay produces the same state as the original execution — a core requirement for auditor-grade systems.

### 7.4 Deployment Governance

`deployment_governance` records every strategy deployment with:
- Strategy ID, deployment mode (paper/live), status
- Approval chain
- Activation timestamp

---

## 8. System Flow Diagram

```
                    ┌────────────┐
                    │  SCOUTS    │◄──── News, Social, Market Data
                    └─────┬──────┘
                          │ signals
                          ▼
                    ┌────────────┐
                    │  IDEATOR   │───► Generate strategy specs
                    └─────┬──────┘
                          │ spec
                          ▼
                    ┌────────────┐
                    │   CODER    │───► Generate executable code
                    └─────┬──────┘
                          │ code
                          ▼
                    ┌────────────┐
                    │ BACKTEST   │───► Run minutely backtest
                    └─────┬──────┘
                          │ results
                          ▼
                    ┌────────────┐
                    │ VALIDATOR  │───► Sharpe, drawdown, overfit, cost
                    └─────┬──────┘
                          │ passed?
                          ▼
              ┌───────────┴───────────┐
              │                       │
             YES                     NO
              │                       │
              ▼                       ▼
     ┌────────────────┐     ┌──────────────┐
     │  RISK LAYER    │     │   RETRY /    │
     └───────┬────────┘     │   MUTATE     │
             │              └──────────────┘
             ▼
     ┌────────────────┐
     │  PORTFOLIO     │──► Compute allocation
     └───────┬────────┘
             │
             ▼
     ┌────────────────┐
     │  EXECUTION     │──► Paper trade / Copy trade
     └───────┬────────┘
             │
             ▼
     ┌────────────────┐
     │  META LAYER    │──► Analyze, mutate, retire
     └────────────────┘
```

---

## 9. Key Architectural Decisions

| Decision | Rationale |
|---|---|
| **7-layer agent architecture** | Clean separation of concerns; layers can be scaled independently |
| **TimescaleDB + PostgreSQL** | Time-series optimization for market data + JSONB flexibility for metrics |
| **Redis pub/sub** | Real-time agent communication without coupling |
| **LLM-generated strategies** | Unbounded strategy search space vs fixed template library |
| **Institutional validation** | Full walk-forward, Monte Carlo, overfitting, and cost stress analysis |
| **Event sourcing** | Full audit trail with replay verification |
| **Copy trading architecture** | Leader/follower model with drift monitoring and sync quality |
| **Scout network** | External signal ingestion with trust-weighted consensus |
| **Meta layer** | Self-governing system that adapts to ecological pressure |
