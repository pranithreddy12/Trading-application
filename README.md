# ATLAS — Autonomous Adaptive Trading Ecosystem

> **Version:** 0.1.0 | **Status:** ✅ Certified Production-Ready | **Python:** 3.11+

ATLAS is an autonomous, evolutionary trading system built on a **7-layer agent architecture** with institutional-grade governance, replay audit, and meta-learning intelligence. Strategies are generated, mutated, backtested, validated, and deployed — all without human intervention.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Dashboard & Monitoring](#dashboard--monitoring)
- [API Reference](#api-reference)
- [Agent Ecosystem](#agent-ecosystem)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## System Overview

ATLAS operates **70+ autonomous agents** across 7 layers, forming a closed-loop ecosystem that:

1. **Ingests** real-time market data from Polygon (equities) and Binance (crypto)
2. **Generates** trading strategies using AI-powered ideation and evolutionary mutation
3. **Backtests** strategies with realistic transaction costs, slippage, and latency modeling
4. **Validates** through walk-forward analysis, Monte Carlo simulation, and overfitting detection
5. **Allocates capital** via Kelly criterion, risk-parity, and regime-conditioned optimization
6. **Executes** trades through institutional-grade gateways with dead-letter recovery
7. **Governs** via immutable event sourcing, hash-chained audit ledgers, and deterministic replay

### Certified Performance Metrics

| Metric | Target | Achieved |
|--------|--------|----------|
| Replay Integrity | 1.000 | **1.000** |
| RAM Usage | <500MB | **~140MB** |
| Event Loop Latency | <5ms | **<1ms** |
| Adaptive Quality | >0.85 | **0.95+** |
| Recovery Quality | >0.60 | **0.90+** |
| Dead-Letter Accumulation | 0 | **0** |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   L7 — META-LEARNING                        │
│  Scouts · Synthesis · Specialization · Evolution · Entropy  │
├─────────────────────────────────────────────────────────────┤
│                   L6 — PORTFOLIO & GOVERNANCE               │
│  Intelligence · Allocator · Copy Trader · Kill Switch       │
├─────────────────────────────────────────────────────────────┤
│                   L5 — EXECUTION                            │
│  Gateway · Brokers · Dead-Letter · Recovery · Realism       │
├─────────────────────────────────────────────────────────────┤
│                   L4 — RISK & CAPITAL                       │
│  Systemic Risk · Stress Tests · Capital Preservation        │
├─────────────────────────────────────────────────────────────┤
│                   L3 — BACKTESTING & VALIDATION             │
│  Runner · Walk-Forward · Monte Carlo · Overfitting · Cost   │
├─────────────────────────────────────────────────────────────┤
│                   L2 — STRATEGY GENERATION                  │
│  Ideator · Mutator · Coder · Combiner · Pattern Agent       │
├─────────────────────────────────────────────────────────────┤
│                   L1 — DATA INGESTION                       │
│  Polygon WS/REST · Binance WS/REST · Features · Patterns   │
└─────────────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

---

## Key Features

### Evolutionary Strategy Generation
- **Tournament Selection** for diverse parent pair selection
- **Feature Blacklisting** — empirically proven losers are excluded automatically
- **Threshold Memory** — successful parameter ranges guide new strategy generation
- **Regime-Weighted Ranking** — strategies scored by current market regime fitness

### Institutional-Grade Execution
- **Dead-Letter Queue** — failed orders classified and replayed automatically
- **Copy Trading** — leader-follower replication with drift detection and failover
- **Execution Realism** — simulated fill probability, slippage, latency, and market impact
- **Position Reconciliation** — broker position alignment on startup

### Meta-Learning Intelligence
- **12+ Scout Sources** — regime, liquidity, correlation, execution, news, Reddit, Discord, YouTube
- **Anti-Poisoning Engine** — quarantines unreliable scout sources
- **Hypothesis Engine** — forms and tests market hypotheses with confidence decay
- **Prompt Evolution** — self-improving LLM prompts based on strategy success rates

### Governance & Auditability
- **Immutable Event Store** — append-only, hash-chained event log
- **Audit Ledger** — per-trace_id sequence-gated audit trail
- **Deterministic Replay** — full system state replay with integrity verification
- **Kill Switch** — emergency halt with Slack notification

---

## Prerequisites

| Component | Version | Required |
|-----------|---------|----------|
| Python | 3.11+ | ✅ |
| PostgreSQL | 15+ | ✅ |
| TimescaleDB | latest | ✅ |
| Redis | 7+ | ✅ |
| Docker | latest | Optional |
| Anthropic API Key | — | ✅ (for strategy generation) |
| Polygon API Key | — | ✅ (for equity data) |
| Binance API Key | — | Optional (for crypto data) |

---

## Quick Start

### 1. Clone and Install

```bash
git clone <repository-url>
cd ATLAS
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -e .
```

### 2. Start Infrastructure

```bash
# Using Docker (recommended)
docker compose up -d

# This starts:
# - TimescaleDB on port 5433
# - Redis on port 6380
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and database credentials
```

### 4. Initialize Database

```bash
python scripts/run_migration.py
python verify_setup.py
```

### 5. Start the System

```bash
# Start the API server
uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000

# Open dashboard
# http://localhost:8000/dashboard/
```

---

## Configuration

All configuration is managed via environment variables (loaded from `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:password@localhost:5433/atlas` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6380` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | — (required) |
| `POLYGON_API_KEY` | Polygon.io market data API key | — (required for equities) |
| `BINANCE_API_KEY` | Binance exchange API key | — (optional for crypto) |
| `BINANCE_SECRET` | Binance exchange secret | — (optional for crypto) |
| `ALPACA_API_KEY` | Alpaca broker API key | — (optional) |
| `ALPACA_SECRET_KEY` | Alpaca broker secret | — (optional) |
| `SLACK_WEBHOOK_URL` | Slack alert webhook | — (optional) |
| `WATCHLIST` | Comma-separated equity symbols | `SPY,QQQ,AAPL,MSFT,NVDA` |
| `CRYPTO_PAIRS` | Comma-separated crypto pairs | `BTCUSDT,ETHUSDT` |
| `ENVIRONMENT` | `dev`, `staging`, or `prod` | `dev` |

---

## Running the System

### Full Autonomous Pipeline

```bash
# Run the complete pipeline (data → strategy → backtest → execute)
python -m atlas.scripts.run_pipeline
```

### Individual Components

```bash
# Data ingestion (Polygon WebSocket)
python -m atlas.agents.l1_data.polygon_ws_agent

# Data ingestion (Binance WebSocket)
python -m atlas.agents.l1_data.binance_rest_agent

# Feature computation
python -m atlas.agents.l1_data.feature_agent

# Strategy ideation
python -m atlas.agents.l2_strategy.ideator_agent

# Strategy mutation
python -m atlas.agents.l2_strategy.mutator_agent

# Backtesting
python -m atlas.agents.l3_backtest.backtest_runner

# Validation
python -m atlas.agents.l3_backtest.validator_agent

# Copy trading
python -m atlas.agents.l5_execution.copy_trader
```

### Soak Testing

```bash
# 60-minute soak test
python atlas/scripts/run_60min_soak.py

# 24-hour soak test
python atlas/scripts/soak/soak_24h.py

# Full ecosystem activation
python scripts/phase36_full_ecosystem_activation.py
```

---

## Dashboard & Monitoring

The ATLAS dashboard provides real-time visibility into all subsystems:

### Access

```
http://localhost:8000/dashboard/
```

### Dashboard Sections

| Section | Endpoint | Description |
|---------|----------|-------------|
| Overview | `/dashboard/api/overview` | System health, strategy counts, DB stats |
| Pipeline | `/dashboard/api/pipeline` | Strategy lifecycle funnel |
| Traces | `/dashboard/api/traces` | Recent lifecycle events |
| Validation | `/dashboard/api/validation` | Walk-forward, Monte Carlo, overfitting |
| Portfolio | `/dashboard/api/portfolio` | Capital allocation, ensemble trades |
| Scouts | `/dashboard/api/scouts` | Internal + external scout signals |
| Governance | `/dashboard/api/governance/system-health` | System health, replay integrity |
| Risk | `/dashboard/api/risk` | Kill switch, positions, P&L |
| Observability | `/dashboard/api/observability/metrics` | Monitoring fabric metrics |
| Meta-Intelligence | `/dashboard/api/meta-reasoning` | AI advisories and hypotheses |

### WebSocket Live Feed

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/live");
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

---

## API Reference

### Authentication

All protected endpoints require a Bearer token:

```bash
curl -H "Authorization: Bearer <api_key>" http://localhost:8000/strategies
```

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health check |
| `GET` | `/strategies` | List strategies (paginated) |
| `GET` | `/strategies/{id}` | Get strategy details |
| `GET` | `/portfolio` | Portfolio summary |
| `GET` | `/positions` | Open positions |
| `GET` | `/paper_trades` | Paper trade history |
| `GET` | `/risk` | Risk metrics |
| `GET` | `/features/{symbol}` | Feature data |
| `POST` | `/kill_switch/activate` | Emergency halt |
| `POST` | `/kill_switch/deactivate` | Resume trading |

### Governance Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dashboard/api/governance/event-store` | Event store timeline |
| `GET` | `/dashboard/api/governance/audit` | Audit ledger entries |
| `GET` | `/dashboard/api/governance/replay-integrity` | Replay integrity score |
| `GET` | `/dashboard/api/governance/deployments` | Deployment records |

---

## Agent Ecosystem

### Layer 1 — Data Ingestion (6 agents)

| Agent | Function |
|-------|----------|
| `PolygonWebSocketAgent` | Real-time equity data (quotes, trades, aggregates) |
| `PolygonRestAgent` | REST-based equity data fallback |
| `BinanceWebSocketAgent` | Real-time crypto market data |
| `BinanceRestAgent` | REST-based crypto data fallback |
| `FeatureAgent` | Technical indicator computation (RSI, MACD, BB, VWAP, etc.) |
| `HistoricalBackfill` | Historical data backfill |

### Layer 2 — Strategy Generation (6 agents)

| Agent | Function |
|-------|----------|
| `IdeatorAgent` | Strategy idea generation from scout signals |
| `IdeatorAgentV2` | Enhanced generation with regime conditioning and threshold memory |
| `MutatorAgent` | Evolutionary strategy mutation with tournament selection |
| `CoderAgent` | Strategy code generation (executable Python) |
| `CombinerAgent` | Strategy combination and blending |
| `MutationPatternAgent` | Mutation pattern analysis |

### Layer 3 — Backtesting & Validation (8 agents)

| Agent | Function |
|-------|----------|
| `BacktestRunner` | Full historical backtesting engine |
| `ValidatorAgent` | Strategy validation and composite scoring |
| `ShortWindowEvaluator` | Short-window performance assessment |
| `WalkForwardAnalyzer` | Temporal consistency verification |
| `MonteCarloSimulator` | Probabilistic outcome simulation |
| `OverfittingDetector` | Parameter stability analysis |
| `RegimeValidator` | Cross-regime robustness checking |
| `CostStressTester` | Transaction cost sensitivity analysis |

### Layer 4 — Risk & Capital (4 agents)

| Agent | Function |
|-------|----------|
| `SystemicRiskEngine` | Contagion and systemic risk monitoring |
| `StressTestEngine` | Scenario-based stress testing |
| `CapitalPreservationEngine` | Drawdown protection and circuit breakers |
| `KillSwitch` | Emergency system halt |

### Layer 5 — Execution (7 agents)

| Agent | Function |
|-------|----------|
| `ExecutionGateway` | Unified order routing |
| `CopyTraderAgent` | Leader-follower trade replication |
| `CopyDriftEngine` | Follower drift detection |
| `CopyFailoverManager` | Failover between followers |
| `DeadLetterManager` | Failed order classification and recovery |
| `RecoveryManager` | Startup reconciliation |
| `PositionReconciliationEngine` | Broker position alignment |

### Layer 6 — Portfolio (6 agents)

| Agent | Function |
|-------|----------|
| `PortfolioIntelligenceEngine` | Portfolio risk/return assessment |
| `CapitalAllocator` | Optimal capital distribution (Kelly, risk-parity) |
| `PortfolioEvolutionPressure` | Adaptive capital migration |
| `AdvancedPortfolioOptimizer` | Mean-variance / risk-parity optimization |
| `CopyOverlapEngine` | Portfolio overlap detection |
| `LeaderGovernanceEngine` | Copy trading leader qualification |

### Layer 7 — Meta-Learning (20+ agents)

| Agent | Function |
|-------|----------|
| `MetaReasoningAgent` | System-wide reasoning and advisories |
| `HypothesisEngine` | Market hypothesis formation and testing |
| `FailureAnalysisEngine` | Root cause analysis of failures |
| `DominantOrganismTracker` | Identifies elite strategies |
| `MutationLineageTracker` | Evolutionary lineage tree tracking |
| `MutationPolicyEngine` | Learns optimal mutation strategies |
| `RegimeSpecializationEngine` | Regime-conditioned fitness profiling |
| `ScoutDivergenceEngine` | Measures scout signal divergence |
| `ScoutSynthesisEngine` | Multi-scout intelligence aggregation |
| `EconomicEfficiencyEngine` | Economic performance analysis |
| `EconomicAttributionEngine` | Credits scout influence on P&L |
| `FeatureImportanceEngine` | Ranks feature predictive power |
| `StrategyRetirementEngine` | Retires underperforming strategies |
| `DriftDetectionEngine` | Detects feature/strategy drift |
| `SystemHealthEngine` | Composite system health scoring |
| `PromptEvolutionEngine` | Self-improving LLM prompts |
| `AntiPoisoningEngine` | Quarantines unreliable scout sources |
| `AgentPerformanceGovernor` | Agent reliability monitoring |
| `DeploymentGovernor` | Strategy deployment approval |

### Scout Network (12+ sources)

| Scout | Data Source |
|-------|-------------|
| `RegimeScout` | Market regime detection (volatility, trend, liquidity) |
| `LiquidityScout` | Order book depth and spread analysis |
| `CorrelationScout` | Cross-asset correlation monitoring |
| `ExecutionScout` | Fill quality and slippage tracking |
| `NewsIntelligenceEngine` | Financial news sentiment |
| `RedditScout` | Reddit sentiment analysis |
| `DiscordScout` | Discord community signals |
| `YouTubeScout` | YouTube content analysis |
| `PodcastScout` | Podcast sentiment extraction |
| `CompetitionScout` | Competitor strategy monitoring |
| `SourceReliabilityEngine` | Dynamic source trust scoring |
| `HypothesisValidationEngine` | Scout signal validation |

---

## Testing

### Run All Tests

```bash
pytest atlas/tests/ -v
```

### Run Specific Test Suites

```bash
# Agent base tests
pytest atlas/tests/test_agent_base.py -v

# Database tests
pytest atlas/tests/test_db.py -v

# Ingestion tests
pytest atlas/tests/test_ingestion.py -v

# L2 Strategy tests
pytest atlas/tests/test_l2_agents.py -v

# L3 Backtest tests
pytest atlas/tests/test_l3_backtest.py -v

# L4 Risk tests
pytest atlas/tests/test_l4_risk.py -v

# L5 Execution tests
pytest atlas/tests/test_l5_execution.py -v

# L7 Meta tests
pytest atlas/tests/test_l7_meta.py -v

# Selection utility tests
pytest atlas/tests/test_selection.py -v
```

### Validation Scripts

```bash
# Full system verification
python verify_setup.py

# Migration verification
python verify_migration.py

# CI pipeline
python scripts/run_ci.py
```

---

## Project Structure

```
ATLAS/
├── atlas/                          # Main application package
│   ├── agents/                     # Agent implementations
│   │   ├── l1_data/               # Data ingestion agents
│   │   ├── l2_strategy/           # Strategy generation agents
│   │   ├── l3_backtest/           # Backtesting & validation agents
│   │   ├── l4_risk/               # Risk management agents
│   │   ├── l5_execution/          # Execution agents
│   │   ├── l6_portfolio/          # Portfolio management agents
│   │   ├── l7_meta/               # Meta-learning agents
│   │   └── scouts/                # Scout network agents
│   ├── api/                        # FastAPI application
│   │   ├── main.py                # API entry point
│   │   └── services/              # API services (auth, etc.)
│   ├── config/                     # Configuration
│   │   └── settings.py            # Pydantic settings
│   ├── core/                       # Core infrastructure
│   │   ├── agent_base.py          # BaseAgent ABC
│   │   ├── event_store.py         # Immutable event log
│   │   ├── audit_ledger.py        # Hash-chained audit trail
│   │   ├── messaging.py           # Redis pub/sub messaging
│   │   ├── selection.py           # Tournament selection
│   │   ├── persistence_integrity.py # UUID normalization, schema contracts
│   │   ├── execution_cost_intelligence.py # Cost modeling
│   │   └── meta_orchestrator.py   # Agent lifecycle management
│   ├── dashboard/                  # Dashboard UI
│   │   ├── router.py              # Dashboard API routes
│   │   ├── templates/             # HTML templates
│   │   ├── control_plane/         # Control plane routes
│   │   └── system_visualization/  # System viz routes
│   ├── data/                       # Data layer
│   │   ├── storage/               # Database clients
│   │   │   ├── timescale_client.py # TimescaleDB client
│   │   │   ├── schema.sql         # Database schema
│   │   │   └── init_timescale.sql # TimescaleDB init
│   │   ├── ingestion/             # Data ingestion clients
│   │   ├── features/              # Feature engineering
│   │   └── sql/                   # SQL utilities
│   ├── governance/                 # Governance modules
│   ├── observability/              # Monitoring & observability
│   │   ├── monitoring_fabric.py   # Distributed metrics
│   │   └── anomaly_monitor.py     # Anomaly detection
│   ├── scripts/                    # Operational scripts
│   │   ├── run_pipeline.py        # Full pipeline runner
│   │   ├── soak/                  # Soak test scripts
│   │   └── migrations/            # Database migrations
│   └── tests/                      # Test suite
├── docs/                           # Documentation
│   ├── architecture.md            # Architecture overview
│   ├── setup_deployment.md        # Setup guide
│   ├── agent_ecosystem.md         # Agent catalog
│   ├── execution_flow.md          # Execution flow diagrams
│   ├── replay_governance.md       # Replay & governance
│   ├── mutation_evolution.md      # Evolutionary system
│   ├── demo_walkthrough.md        # Demo guide
│   ├── certification_summary.md   # Certification status
│   └── reports/                   # Phase reports
├── scripts/                        # Top-level scripts
│   ├── run_ci.py                  # CI runner
│   ├── run_migration.py           # Migration runner
│   └── run_deployment_governor.py # Deployment governor
├── docker-compose.yml              # Docker infrastructure
├── pyproject.toml                  # Python project config
└── conftest.py                     # Pytest configuration
```

---

## Deployment

### Docker Deployment (Recommended)

```bash
# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Scale specific agents
docker compose up -d --scale mutator=3
```

### Manual Deployment

```bash
# 1. Install dependencies
pip install -e .

# 2. Start infrastructure
docker compose up -d timescaledb redis

# 3. Run migrations
python scripts/run_migration.py

# 4. Start API server
uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000

# 5. Start agents (in separate terminals or using process manager)
python -m atlas.agents.l1_data.polygon_ws_agent &
python -m atlas.agents.l1_data.feature_agent &
python -m atlas.agents.l2_strategy.ideator_agent &
python -m atlas.agents.l3_backtest.backtest_runner &
```

### Production Checklist

- [ ] Environment variables configured in `.env`
- [ ] Database migrations applied (`python scripts/run_migration.py`)
- [ ] Schema contracts validated (`python verify_setup.py`)
- [ ] API server responding on port 8000
- [ ] Dashboard accessible at `/dashboard/`
- [ ] Redis connected and pub/sub working
- [ ] At least one data feed active (Polygon or Binance)
- [ ] Kill switch tested (`POST /kill_switch/activate` then `/deactivate`)
- [ ] Replay integrity score = 1.000
- [ ] Slack webhook configured for alerts

### Database Schema

ATLAS uses **TimescaleDB** (PostgreSQL + hypertables) with 40+ tables:

| Table Group | Tables | Purpose |
|-------------|--------|---------|
| **Core** | `strategies`, `backtest_results`, `backtest_trades` | Strategy lifecycle |
| **Data** | `market_data_l1`, `features`, `features_wide` | Market data & features |
| **Scouts** | `scout_signals`, `market_regime_memory`, `liquidity_intelligence` | Scout network |
| **Governance** | `event_store`, `audit_ledger`, `deployment_governance` | Audit & governance |
| **Portfolio** | `portfolio_intelligence`, `capital_allocation`, `ensemble_execution` | Portfolio mgmt |
| **Risk** | `systemic_risk`, `stress_test_results`, `capital_preservation_state` | Risk management |
| **Copy Trading** | `copy_position_state`, `copy_drift_log`, `leader_health_metrics` | Copy trading |
| **Meta** | `hypothesis_registry`, `mutation_policy_state`, `meta_reasoning_log` | Meta-learning |
| **Observability** | `monitoring_metrics`, `anomaly_observations` | Monitoring |

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `DATABASE_URL not set` | Ensure `.env` file exists with `DATABASE_URL` |
| `Connection refused (5433)` | Start TimescaleDB: `docker compose up -d timescaledb` |
| `Connection refused (6380)` | Start Redis: `docker compose up -d redis` |
| `Schema contract validation failed` | Run `python scripts/run_migration.py` |
| `ANTHROPIC_API_KEY missing` | Add key to `.env` file |
| Agent restart storms | Check `_min_restart_interval` in `agent_base.py` |
| Dead-letter accumulation | Check `execution_log` table for failed orders |

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "agents_alive": 5,
  "agents_dead": 0,
  "kill_switch_active": false,
  "latency_ms": 1,
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "api": "healthy"
  }
}
```

### Logs

```bash
# API server logs
tail -f api_server.log

# Pipeline logs
tail -f atlas/soak.log

# Phase-specific logs
tail -f atlas/phase25_soak_pipeline.log
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System architecture and design principles |
| [Setup & Deployment](docs/setup_deployment.md) | Installation and deployment guide |
| [Agent Ecosystem](docs/agent_ecosystem.md) | Complete agent catalog |
| [Execution Flow](docs/execution_flow.md) | End-to-end execution flow diagrams |
| [Replay & Governance](docs/replay_governance.md) | Event sourcing and audit system |
| [Mutation & Evolution](docs/mutation_evolution.md) | Evolutionary strategy system |
| [Demo Walkthrough](docs/demo_walkthrough.md) | Step-by-step demo guide |
| [Certification](docs/certification_summary.md) | Production readiness certification |

---

## Support

- **Documentation:** See `docs/` directory
- **Issues:** Report via project issue tracker
- **Architecture:** See `docs/architecture.md`

---

## License

Proprietary — All rights reserved.

---

*ATLAS — Built with institutional-grade rigor for autonomous trading.*
