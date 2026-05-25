# ATLAS Documentation Index

**Institutional-Grade Autonomous Trading System**

---

Welcome to the ATLAS documentation. This index maps the project structure and provides quick navigation to all documentation and key source modules.

---

## 1. Quick Reference

| Document | Description |
|---|---|
| [`docs/architecture.md`](architecture.md) | System architecture — 7-layer agent model, core infrastructure, API, governance |
| [`docs/setup.md`](setup.md) | Setup guide — dependencies, configuration, database, deployment, troubleshooting |
| [`docs/execution_flow.md`](execution_flow.md) | Strategy lifecycle — ideation → coding → backtest → validation → execution → meta |
| `memory.md` (root) | System memory and evolutionary state — key metrics and historical context |

---

## 2. Project Structure

```
atlas/                              # Python package (editable install)
│
├── api/                            # FastAPI REST API layer
│   ├── main.py                     # App entry, routes, WebSocket, middleware
│   ├── day4_api.py                 # Legacy API version
│   ├── contracts/                  # API contract definitions
│   ├── middleware/                  # Auth, rate limiting
│   ├── routes/                     # Route-specific handlers
│   └── services/                   # Business logic (auth, copy, health, risk)
│
├── agents/                         # Agent implementations (7-layer architecture)
│   │
│   ├── l2_strategy/                # L2 — Strategy Generation
│   │   ├── ideator_agent_v2.py     # LLM-powered strategy spec generation
│   │   ├── coder_agent.py          # Converts specs → executable Python code
│   │   └── strategy_normalizer.py  # Normalizes strategy parameters
│   │
│   ├── l3_backtest/                # L3 — Backtesting & Validation
│   │   ├── backtest_runner.py      # Minutely OHLCV backtest engine
│   │   ├── validator_agent.py      # Institutional validation rules
│   │   └── short_window_evaluator.py # Short-window performance assessment
│   │
│   ├── l3_validation/              # L3 — Advanced Validation
│   │   └── regime_validator.py     # Multi-regime survival validation
│   │
│   ├── l4_risk/                    # L4 — Risk Management
│   │   └── risk_controller.py      # Risk governance, position limits
│   │
│   ├── l5_execution/               # L5 — Order Execution
│   │   ├── execution_gateway.py    # Trade execution engine
│   │   └── order_tracker.py        # Order lifecycle tracking
│   │
│   ├── l6_portfolio/               # L6 — Portfolio Intelligence
│   │   └── portfolio_intelligence_engine.py # Allocation, diversification, drift
│   │
│   ├── l7_meta/                    # L7 — Meta Intelligence
│   │   ├── meta_reasoning_agent.py # System-wide advisories
│   │   ├── mutation_policy_engine.py # Exploration vs exploitation control
│   │   ├── failure_analysis_engine.py # Root cause analysis
│   │   ├── feature_evolution_engine.py # Feature lifecycle tracking
│   │   ├── hypothesis_engine.py    # Belief registry with evidence tracking
│   │   ├── scout_synthesis_engine.py # Scout consensus scoring
│   │   ├── system_health_engine.py # Composite health assessment
│   │   ├── anti_poisoning_engine.py # Adversarial signal filtering
│   │   └── strategy_retirement_engine.py # Underperformer retirement
│   │
│   └── scouts/                     # L1 — Scout Network
│       ├── hypothesis_validation_engine.py # Hypothesis testing
│       ├── news_intelligence_engine.py     # News sentiment processing
│       └── source_reliability_engine.py    # Source trust scoring
│
├── core/                           # System Foundation
│   ├── agent_base.py               # Abstract base agent
│   ├── meta_orchestrator.py        # Pipeline orchestration
│   ├── messaging.py                # Redis pub/sub messaging
│   ├── claude_client.py            # LLM API client
│   ├── score_contract.py           # Strategy scoring schema
│   ├── execution_cost_intelligence.py # Cost governance engine
│   └── event_lineage.py            # Causal tracing system
│
├── config/                         # Configuration
│   └── settings.py                 # Centralized environment-based settings
│
├── data/                           # Data Layer
│   └── storage/
│       └── timescale_client.py     # TimescaleDB async client
│
├── dashboard/                      # Operator Dashboard
│   ├── templates/index.html        # Single-page HTML dashboard
│   ├── router.py                   # Dashboard API endpoints
│   ├── control_plane/              # Operator management endpoints
│   └── system_visualization/       # Graph visualization endpoints
│
├── observability/                  # Observability
│   ├── monitoring_fabric.py        # Real-time metrics collection
│   └── anomaly_monitor.py          # Anomaly detection engine
│
├── docs/                           # Documentation (this directory)
│   ├── README.md                   # This file — documentation index
│   ├── architecture.md             # System architecture overview
│   ├── setup.md                    # Setup & deployment guide
│   └── execution_flow.md           # Strategy lifecycle flow
│
├── scripts/                        # Run scripts & utilities
│   ├── run_pipeline.py             # Full pipeline launcher
│   ├── run_execution_chain.py      # Execution engine launcher
│   ├── run_mutator.py              # Mutation engine launcher
│   ├── full_autonomous_cycle.py    # Complete autonomous cycle
│   ├── seed_historical_data.py     # Market data seeding
│   ├── seed_equity_data.py         # Equity data seeding
│   ├── historical_ingest.py        # Data ingestion
│   ├── historical_feature_bootstrap.py # Feature bootstrapping
│   ├── batch_reprocess_all.py      # Batch reprocessing
│   ├── generate_delivery_reports.py # Report generation
│   ├── pre_delivery_precheck.py    # Pre-deployment validation
│   └── soak/                       # Soak test scripts
│       ├── phase28_economic_soak.py
│       └── phase29_economic_survival_soak.py
│
├── tests/                          # Test Suite (193 tests)
│   ├── test_agent_base.py          # Agent lifecycle tests
│   ├── test_db.py                  # Database operations
│   ├── test_features.py            # Feature extraction
│   ├── test_ingestion.py           # Data ingestion
│   ├── test_internal_scout_network.py # Scout network
│   ├── test_l2_agents.py           # L2 strategy agents
│   ├── test_l3_backtest.py         # L3 backtest & validation
│   ├── test_l4_risk.py             # L4 risk management
│   ├── test_l5_execution.py        # L5 execution engine
│   ├── test_l7_meta.py             # L7 meta intelligence
│   ├── test_phase19_meta_intelligence.py # Phase 19 extensions
│   └── chaos/                      # Chaos engineering tests
│       └── test_scout_corruption.py # Malformed signal rejection
│
├── requirements.txt                # Python dependencies
├── .env                            # Environment configuration
└── memory.md                       # System evolutionary memory
```

---

## 3. Module Dependency Map

```
core/agent_base.py
    ├── core/messaging.py
    ├── core/claude_client.py
    └── data/storage/timescale_client.py

agents/l2_strategy/ideator_agent_v2.py
    ├── core/agent_base.py
    ├── core/score_contract.py
    ├── config/settings.py
    └── agents/scouts/*.py (indirect)

agents/l3_backtest/backtest_runner.py
    ├── core/agent_base.py
    └── core/execution_cost_intelligence.py

agents/l3_backtest/validator_agent.py
    ├── core/agent_base.py
    ├── core/execution_cost_intelligence.py
    └── core/score_contract.py

agents/l5_execution/execution_gateway.py
    ├── core/agent_base.py
    └── agents/l4_risk/risk_controller.py

agents/l7_meta/meta_reasoning_agent.py
    ├── core/agent_base.py
    ├── agents/l7_meta/hypothesis_engine.py
    ├── agents/l7_meta/system_health_engine.py
    └── agents/l7_meta/scout_synthesis_engine.py

api/main.py
    ├── config/settings.py
    ├── data/storage/timescale_client.py
    ├── dashboard/router.py
    └── api/services/*.py
```

---

## 4. Database Schema (Primary Tables)

| Table | Purpose | Key Columns |
|---|---|---|
| `strategies` | Strategy lifecycle | id, name, status, spec, code, created_at |
| `backtest_results` | Backtest metrics | strategy_id, sharpe, drawdown, total_return, profit_factor |
| `execution_log` | Trade execution | order_key, strategy_id, symbol, side, qty, price, state |
| `paper_trades` | Paper trade log | strategy_name, symbol, pnl, entry_time, exit_time |
| `portfolio_intelligence` | Portfolio snapshots | n_strategies, diversification_score, optimal_allocations |
| `capital_allocation` | Capital deployment | method, total_exposure, final_allocations |
| `lifecycle_events` | Event tracing | trace_id, stage, status, actor, strategy_id |
| `event_store` | Event sourcing | aggregate_type, event_type, trace_id, payload |
| `audit_ledger` | Operator audit trail | actor, action, target_id, trace_id |
| `mutation_memory` | Strategy lineage | parent_id, child_id, mutation_type, sharpe_delta |
| `external_scout_memory` | Scout signals | source, sentiment, hypothesis_score, signal_direction |
| `pattern_memory` | Learned patterns | pattern_type, archetype, confidence_score |
| `system_health` | Health assessments | composite_score, system_mode, degraded_subsystems |
| `monitoring_metrics` | Telemetry | counters, latencies |

---

## 5. Configuration Reference

All configuration is managed through `config/settings.py` and loaded from `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | TimescaleDB connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `ENVIRONMENT` | `dev` | Runtime environment (dev/staging/production) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_STRATEGIES_PER_CYCLE` | `5` | Strategy generation throttle |
| `CLAUDE_API_KEY` | — | Anthropic API key |
| `ALPACA_API_KEY` | — | Alpaca trading API key |
| `ALPACA_SECRET_KEY` | — | Alpaca API secret |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Alpaca endpoint |
| `TWITTER_BEARER_TOKEN` | — | Twitter/X API token |
| `NEWS_API_KEY` | — | News API key |

---

## 6. Agent Communication Channels (Redis)

| Channel | Publisher | Subscribers | Payload |
|---|---|---|---|
| `strategy:spec` | IdeatorAgent | CoderAgent | Strategy specification |
| `strategy:code` | CoderAgent | BacktestRunner | Generated Python code |
| `strategy:backtest` | BacktestRunner | ValidatorAgent | Backtest results |
| `strategy:validated` | ValidatorAgent | PortfolioEngine | Validated strategy |
| `strategy:deployed` | PortfolioEngine | ExecutionGateway | Allocation decision |
| `trade:executed` | ExecutionGateway | All agents | Execution event |
| `scout:signal` | Scout agents | L7 Meta agents | External intelligence |
| `agent:heartbeat` | All agents | SystemHealth | Health monitoring |
| `agent:control` | ControlPlane | Target agent | Operational commands |
| `risk:kill_switch` | KillSwitch | All agents | Emergency stop events |

---

## 7. Key Metrics

| Metric | Target | Measurement |
|---|---|---|
| Test suite | 193/193 passing | `python -m pytest tests/` |
| Strategy generation rate | Configurable | `MAX_STRATEGIES_PER_CYCLE` |
| Backtest window | 60 minutes minutely | `_run_backtest` |
| Validation latency | < 5 seconds | Per strategy |
| Execution latency | < 100ms copy trading | `copy_execution_log.latency_ms` |
| Soak duration | 6h / 12h / 24h | `phase28_economic_soak.py` |
| Anomaly detection | < 1% false positive | `anomaly_monitor.py` |
| Production validation | Sharpe ≥ 1.0, trades ≥ 30 | `validator_agent.py` |
