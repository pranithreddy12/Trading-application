# ATLAS — Architecture Deep Dive

This document provides a comprehensive technical overview of the ATLAS system architecture, data flows, and design decisions.

---

## Table of Contents

- [Design Principles](#design-principles)
- [System Architecture](#system-architecture)
- [Layer Specifications](#layer-specifications)
- [Data Flow](#data-flow)
- [Database Architecture](#database-architecture)
- [Messaging & Communication](#messaging--communication)
- [Agent Lifecycle](#agent-lifecycle)
- [Governance Model](#governance-model)
- [Evolutionary System](#evolutionary-system)
- [Scout Network](#scout-network)
- [Deployment Modes](#deployment-modes)

---

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Deterministic** | Canonical UUIDs for all mutations, replay, and governance events |
| **Immutable** | Event store and audit ledger are append-only with hash chaining |
| **Evolutionary** | Strategies mutate, compete, and are selected by economic fitness |
| **Self-governing** | Health checks, kill switches, and performance governors |
| **Scout-driven** | 12+ intelligence scouts feed the meta-learning layer |
| **Advisory-only** | Meta-layer agents produce recommendations, never mutate state directly |
| **Idempotent** | All operations can be safely retried without side effects |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          L7 — META-LEARNING                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │  Scout   │ │  Meta    │ │ Dominant │ │ Mutation │ │  Regime  │ │
│  │ Synthesis│ │ Reasoning│ │ Organism │ │  Policy  │ │Specializ.│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │            │            │            │            │         │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ │
│  │  Failure │ │ Hypothesis│ │ Economic │ │  Prompt  │ │ Strategy │ │
│  │ Analysis │ │  Engine  │ │Attribut. │ │Evolution │ │Retirement│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                        L6 — PORTFOLIO & GOVERNANCE                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Portfolio │ │ Capital  │ │  Copy    │ │  Copy    │ │  Leader  │ │
│  │Intelligen│ │Allocator │ │  Trader  │ │  Drift   │ │Governance│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                          L5 — EXECUTION                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Execution │ │  Broker  │ │   Dead   │ │Recovery  │ │Execution │ │
│  │ Gateway  │ │ Adapters │ │ Letter   │ │ Manager  │ │ Realism  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                        L4 — RISK & CAPITAL                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Systemic │ │  Stress  │ │ Capital  │ │   Kill   │              │
│  │   Risk   │ │   Test   │ │Preservat.│ │  Switch  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
├─────────────────────────────────────────────────────────────────────┤
│                      L3 — BACKTESTING & VALIDATION                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Backtest  │ │  Walk    │ │  Monte   │ │Overfitting│ │  Cost   │ │
│  │ Runner   │ │ Forward  │ │  Carlo   │ │ Detector │ │Stress T.│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                       L2 — STRATEGY GENERATION                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Ideator  │ │ Mutator  │ │  Coder   │ │ Combiner │ │ Pattern  │ │
│  │ (V1 + V2)│ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                        L1 — DATA INGESTION                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Polygon  │ │ Binance  │ │ Feature  │ │Historical│ │ Pattern  │ │
│  │ WS/REST  │ │ WS/REST  │ │  Agent   │ │ Backfill │ │Recognition│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer Specifications

### L1 — Data Ingestion & Features

**Purpose:** Capture, normalize, and persist market data; compute technical indicators.

| Component | Protocol | Data Model |
|-----------|----------|------------|
| `PolygonWebSocketAgent` | WebSocket (wss://) | Quotes (Q.*), Trades (T.*), Aggregates (A.*) |
| `PolygonRestAgent` | REST (HTTPS) | Historical bars, snapshots |
| `BinanceWebSocketAgent` | WebSocket (wss://) | Trades (@trade), Depth (@depth20@100ms) |
| `BinanceRestAgent` | REST (HTTPS) | Historical klines, orderbook snapshots |
| `FeatureAgent` | Internal (DB) | 22+ technical indicators per symbol |

**Key Features Computed:**
- RSI (14-period)
- MACD (12/26/9)
- Bollinger Bands (20-period, 2σ)
- VWAP deviation percentage
- EMA spread percentage
- Relative volume
- Volatility regime
- Trend strength
- Bollinger band position

**Data Models (TimescaleDB):**
- `market_data_l1` — Raw OHLCV bars (hypertable, partitioned by time)
- `features` — Long-format technical indicators
- `features_wide` — Materialized view (pivot of features)

---

### L2 — Strategy Generation

**Purpose:** Generate, mutate, and combine trading strategies using AI and evolutionary algorithms.

#### IdeatorAgent (V1)
- Generates strategy specs from scout signals
- Uses Claude LLM for strategy design
- Template-based entry/exit condition generation
- Feature blacklisting (empirically proven losers excluded)

#### IdeatorAgentV2 (Enhanced)
- **Regime-conditioned** strategy generation
- **Threshold memory** — successful parameter ranges from backtested strategies
- **Feature distribution** — generates conditions within realistic data ranges
- **Grammar-based** deterministic strategy generation
- **Constraint engine** — validates conditions against market reality

#### MutatorAgent
- **Tournament selection** for candidate prioritization
- Mutation types: parameter, code, blend, regime-adaptive, risk-profile
- Anti-clone detection (avoids near-duplicate strategies)
- Lineage tracking for evolutionary analysis

#### CoderAgent
- Generates executable Python strategy code from specs
- Compiles and validates strategy syntax
- Supports regime-gated entry logic

#### CombinerAgent
- Combines two successful strategies into hybrids
- Tournament selection for parent pair diversity
- Anti-clone checks on combinations

**Strategy Lifecycle:**
```
pending → ideating → coded → backtesting → validated → active → retired
                          ↓
                    backtest_failed
```

---

### L3 — Backtesting & Validation

**Purpose:** Validate strategy viability through comprehensive backtesting and multi-dimensional analysis.

#### BacktestRunner
- Polls `strategies` table for `pending_backtest` status
- Loads historical data for the strategy's symbol
- Computes features on-the-fly
- Executes strategy signal generation
- Calculates performance metrics
- Handles consecutive error recovery

**Performance Metrics Computed:**
| Metric | Formula |
|--------|---------|
| Sharpe Ratio | (Mean Return - Risk-Free Rate) / Std Dev |
| Sortino Ratio | (Mean Return - Risk-Free) / Downside Dev |
| Calmar Ratio | Annualized Return / Max Drawdown |
| Expectancy | (Win Rate × Avg Win) - (Loss Rate × Avg Loss) |
| Composite Fitness | Weighted combination of above |

#### Validation Suite

| Validator | Purpose |
|-----------|---------|
| `WalkForwardAnalyzer` | Tests strategy across rolling time windows |
| `MonteCarloSimulator` | Runs N random trade shuffles for probabilistic assessment |
| `OverfittingDetector` | Measures parameter stability under noise injection |
| `RegimeValidator` | Tests strategy across market regimes (bull, bear, ranging, high_vol) |
| `CostStressTester` | Varies transaction costs to find survival threshold |

**Validation Score Thresholds:**
| Score Component | Weight | Min Threshold |
|-----------------|--------|---------------|
| Composite Fitness | 30% | >0.5 |
| Walk-Forward Score | 20% | >0.4 |
| Monte Carlo Survival | 15% | >0.6 |
| Overfitting Robustness | 15% | >0.3 |
| Regime Survival | 10% | >2 regimes |
| Cost Survival | 10% | >1.5x costs |

---

### L4 — Risk & Capital

**Purpose:** Manage portfolio-level risk and capital allocation.

#### SystemicRiskEngine
- Monitors cross-strategy contagion risk
- Calculates portfolio fragility scores
- Tracks correlation regime changes
- Generates retirement recommendations

#### StressTestEngine
- Runs crisis scenario simulations
- Tests portfolio under: flash crash, correlation spike, liquidity drain, volatility expansion
- Computes worst-case drawdown and recovery time

#### CapitalPreservationEngine
- Monitors drawdown against thresholds
- Reduces exposure during drawdowns
- Triggers circuit breakers at critical levels

#### KillSwitch
- Emergency halt of all trading
- Slack notification on activation
- Database-backed state (persisted across restarts)

**Risk Thresholds:**
| Metric | Warning | Critical | Kill Switch |
|--------|---------|----------|-------------|
| Daily Loss | >1% | >3% | >5% |
| Max Drawdown | >5% | >10% | >15% |
| Concentration | >30% | >50% | >70% |
| Systemic Risk | >0.5 | >0.7 | >0.9 |

---

### L5 — Execution

**Purpose:** Route orders to brokers, manage copy trading, and handle failures.

#### ExecutionGateway
- Unified order routing across brokers
- Fill simulation with realistic slippage
- Order lifecycle tracking

#### Copy Trading System
- **CopyTraderAgent** — Replicates leader trades to followers
- **CopyDriftEngine** — Detects follower divergence from leader
- **CopyFailoverManager** — Switches followers if leader degrades
- **PositionReconciliationEngine** — Aligns broker positions on startup

#### Dead-Letter Recovery
- Failed orders classified by root cause
- Automatic retry for transient failures
- Manual review queue for persistent failures

#### Execution Realism Engine
- Simulates fill probability based on order size and liquidity
- Models slippage based on market impact
- Estimates execution latency
- Stress tests under liquidity exhaustion

---

### L6 — Portfolio & Governance

**Purpose:** Portfolio optimization, copy trading governance, and system governance.

#### Portfolio Intelligence Engine
- Computes correlation matrix across strategies
- Identifies strategy clusters
- Measures diversification and concentration risk
- Generates optimal allocations

#### Capital Allocator
- **Kelly Criterion** — Optimal bet sizing
- **Risk-Parity** — Equal risk contribution
- **Volatility Targeting** — Position sizing by target vol
- **Regime-Conditioned** — Weights adjusted by market regime

#### Governance Components
- **Event Store** — Immutable append-only event log
- **Audit Ledger** — Hash-chained audit trail
- **Replay Engine** — Deterministic replay verification
- **Deployment Governor** — Strategy deployment approval workflow
- **Leader Governance** — Copy trading leader qualification

---

### L7 — Meta-Learning

**Purpose:** System-level intelligence, evolutionary optimization, and self-improvement.

#### Scout Synthesis
- Aggregates signals from 12+ scout sources
- Computes scout agreement/disagreement scores
- Identifies conflicting signals for investigation

#### Meta Reasoning
- System-wide reasoning and advisories
- Advisory-only mode (never mutates state)
- Tracks confidence and reasoning quality

#### Evolutionary Intelligence
- **DominantOrganismTracker** — Identifies and tracks elite strategies
- **MutationLineageTracker** — Builds evolutionary trees
- **MutationPolicyEngine** — Learns optimal mutation strategies
- **RegimeSpecializationEngine** — Profiles regime-conditioned fitness

#### Economic Intelligence
- **EconomicEfficiencyEngine** — Analyzes system-wide economic performance
- **EconomicAttributionEngine** — Credits scout signals for P&L impact
- **FeatureImportanceEngine** — Ranks feature predictive power

#### Self-Improvement
- **PromptEvolutionEngine** — Evolves LLM prompts based on success rates
- **AntiPoisoningEngine** — Quarantines unreliable scout sources
- **HypothesisEngine** — Forms and tests market hypotheses

---

## Data Flow

### Strategy Lifecycle Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scout     │────▶│   Ideator   │────▶│   Coder     │
│   Signals   │     │   Agent     │     │   Agent     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Portfolio  │◀────│  Validator  │◀────│  Backtest   │
│  Allocator  │     │   Agent     │     │   Runner    │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Execution  │────▶│  Event      │────▶│   Audit     │
│  Gateway    │     │  Store      │     │   Ledger    │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Economic   │────▶│  Strategy   │     │   Replay    │
│ Attribution │     │  Retirement │     │   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Event Sourcing Flow

```
Action ──▶ Event Store ──▶ Hash Chain ──▶ Audit Ledger
   │                          │                  │
   │                          ▼                  ▼
   │                    Integrity Check    Trace Verification
   │                          │                  │
   └──────────────────────────┴──────────────────┘
                              │
                              ▼
                    Replay Verification
```

---

## Database Architecture

### TimescaleDB Hypertables

| Table | Partitioning | Retention |
|-------|-------------|-----------|
| `market_data_l1` | By `time` (1-hour chunks) | 90 days |
| `features` | By `time` (1-hour chunks) | 90 days |
| `backtest_results` | Standard table | Indefinite |
| `strategies` | Standard table | Indefinite |
| `event_store` | Standard table | Indefinite |
| `audit_ledger` | Standard table | Indefinite |

### Key Indexes

```sql
-- Strategy lookup
CREATE INDEX idx_strategies_status ON strategies (status);
CREATE INDEX idx_strategies_trace ON strategies (trace_id);
CREATE INDEX idx_strategies_lifecycle ON strategies (lifecycle_state);

-- Backtest results
CREATE INDEX idx_backtest_strategy ON backtest_results (strategy_id);
CREATE INDEX idx_backtest_fitness ON backtest_results (composite_fitness_score DESC);

-- Event store
CREATE INDEX idx_events_aggregate ON event_store (aggregate_id);
CREATE INDEX idx_events_trace ON event_store (trace_id);
CREATE INDEX idx_events_created ON event_store (created_at DESC);

-- Scout signals
CREATE INDEX idx_scout_signals_source ON scout_signals (source);
CREATE INDEX idx_scout_signals_created ON scout_signals (created_at DESC);
```

### Materialized Views

| View | Purpose | Refresh |
|------|---------|---------|
| `features_wide` | Pivoted features for strategy evaluation | On-demand |

---

## Messaging & Communication

### Redis Pub/Sub Channels

| Channel | Publisher | Subscribers |
|---------|-----------|-------------|
| `market_data` | L1 agents | L2 agents |
| `strategy_signals` | L2 agents | L3 agents |
| `risk_alerts` | L4 agents | L5 agents, L7 agents |
| `execution_fills` | L5 agents | L6 agents, L7 agents |
| `system_events` | All agents | L7 agents, Dashboard |

### Agent Heartbeats

Each agent publishes a heartbeat to Redis every 10 seconds:

```
Key: agent:<agent_id>
Fields: status, layer, name, agent_type, advisory_only
TTL: 30 seconds
```

The `MetaOrchestrator` monitors heartbeats and restarts dead agents.

---

## Agent Lifecycle

### BaseAgent Contract

```python
class BaseAgent(ABC):
    async def start()     # Begin execution
    async def stop()      # Graceful shutdown
    async def pause()     # Pause without stopping
    async def resume()    # Resume from pause
    async def run()       # Main execution loop (abstract)
```

### Retry Logic

```python
MAX_RETRIES = 3
backoff = 2 ** retry_count  # Exponential: 2s, 4s, 8s
_min_run_duration = 60.0    # Prevent tight restart loops
_min_restart_interval = 30.0 # Minimum time between starts
```

### Advisory-Only Guard

Meta-layer agents are marked `advisory_only=True` and cannot:
- Place orders
- Allocate capital
- Override governance
- Mutate execution state

They can only produce persisted recommendations.

---

## Governance Model

### Event Store

```
Event N-1                    Event N                     Event N+1
┌──────────────┐            ┌──────────────┐            ┌──────────────┐
│ event_id     │            │ event_id     │            │ event_id     │
│ aggregate_id │──────────▶ │ aggregate_id │──────────▶ │ aggregate_id │
│ prev_hash    │            │ prev_hash    │            │ prev_hash    │
│ hash         │            │ hash         │            │ hash         │
│ created_at   │            │ created_at   │            │ created_at   │
│ payload      │            │ payload      │            │ payload      │
└──────────────┘            └──────────────┘            └──────────────┘
```

### Audit Ledger

- Per-`trace_id` sequence numbering
- Hash chaining for tamper detection
- Immutable append-only

### Replay Integrity Score

```
integrity_score = (1 - violations / total_events) × 100
```

A score of **100** means perfect replay integrity.

---

## Evolutionary System

### Mutation Types

| Type | Description | Typical Effect |
|------|-------------|----------------|
| **Parameter** | Adjust thresholds, periods, limits | Low variance |
| **Code** | Modify entry/exit logic | Medium variance |
| **Blend** | Combine two strategies | High variance |
| **Regime-adaptive** | Add regime detection | Medium variance |
| **Risk-profile** | Vary position sizing | Low variance |

### Selection Pressure

- **Composite Fitness** — Weighted: Sharpe, Sortino, Calmar, expectancy
- **Retirement** — Bottom performers retired automatically
- **Capital Migration** — Capital shifted from weak to strong strategies
- **Dominant Boost** — Top strategies receive amplified allocation

### Lineage Tracking

```
Strategy A (parent)
├── Mutation A1 (child)
│   ├── Mutation A1a (dominant — highest fitness)
│   └── Mutation A1b (retired — low fitness)
├── Mutation A2
│   └── Mutation A2a
└── Mutation A3 (retired)
```

---

## Scout Network

### Internal Scouts

| Scout | Data Source | Signal Type |
|-------|-------------|-------------|
| `RegimeScout` | Market data | Volatility/trend regime |
| `LiquidityScout` | Order book | Spread, depth, slippage risk |
| `CorrelationScout` | Cross-asset data | Correlation regime |
| `ExecutionScout` | Trade logs | Fill quality, latency |

### External Scouts

| Scout | Data Source | Signal Type |
|-------|-------------|-------------|
| `NewsIntelligenceEngine` | Financial news | Sentiment, mention frequency |
| `RedditScout` | Reddit API | Community sentiment |
| `DiscordScout` | Discord API | Community signals |
| `YouTubeScout` | YouTube API | Content sentiment |
| `PodcastScout` | Podcast feeds | Audio sentiment |

### Anti-Poisoning

The `AntiPoisoningEngine` monitors scout signal quality and:
- Detects anomalous signal patterns
- Quarantines unreliable sources
- Adjusts dynamic trust scores
- Prevents poisoned signals from influencing strategy generation

---

## Deployment Modes

### Paper Trading (Default)

- Simulated execution only
- No real orders placed
- Full governance and audit trail
- Safe for development and testing

### Live Trading

- Real broker connections (Binance, Alpaca)
- Full risk management active
- Kill switch enabled
- Deployment governor approval required

### Hybrid Mode

- Paper trading for new strategies
- Live trading for validated strategies
- Automatic promotion based on performance

---

*Last updated: June 2026*
