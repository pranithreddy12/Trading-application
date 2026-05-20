# ATLAS PROJECT MEMORY FILE
> Last Updated: Day 3 — May 13, 2026 (Evening Update)
> Purpose: Full project context for continuing development if conversation resets

---

## 1. WHAT IS THIS PROJECT

**ATLAS** = Autonomous Trading & Learning Agent System
**Client** = Shah Quantum Fund (SQF), Karachi — represented by **Amit Bhosla**
**Our Role** = Engineering contractor building the full system

ATLAS is a self-running AI trading company made of 94 agents across 7 layers.
It finds trading ideas, writes the code, backtests it, manages risk, and executes
trades — all automatically, 24/7, with no human intervention.

---

## 2. BUSINESS AGREEMENT

| Item | Detail |
|---|---|
| Phase 1 value | $3,000 (3 milestones × $1,000) |
| Phase 2 value | $2,000 |
| Completion bonus | $1,000 (both phases on time) |
| Total max | $6,000 USD (~₹5,60,000) |
| Phase 1 timeline | 5–7 working days |
| Phase 2 timeline | 5–7 working days (starts 2–3 days after Phase 1 acceptance) |
| Team size | 3 engineers |
| Competition | Multiple teams building same project — best output wins ongoing work |
| Non-compete | 12 months post-engagement, agent-based trading systems |

### Phase 1 Scope (our commitment)
- Full AWS infrastructure
- L1 Data ingestion (Polygon.io equities + Binance crypto)
- Feature engineering pipeline (50+ features)
- Agent registry + Meta-Orchestrator
- L2 Strategy agents (Ideator ×5, Coder, Combiner, Mutator) via Claude API
- L3 Backtest Runners + Validation (6 tests)
- L4 Risk Management + Kill Switch
- L5 Paper execution (Alpaca + Binance)
- Self-improvement loop (fully coded, runs on paper trading data)
- Dashboard REST APIs + WebSocket
- Daily Intelligence Brief auto-generation
- 20–30 strategies generated, backtested, validated
- Full documentation

### Phase 2 Scope (separate contract)
- Scout Network (7 platform integrations: YouTube, Discord, Reddit,
  Twitter, Telegram, Instagram, Upwork/Kaggle)
- Copy Trading + Fidelity Monitoring agents
- 100+ validated strategies

---

## 3. MILESTONE STRUCTURE

### Milestone 1 — Infrastructure & Data Foundation — $1,000
**Days 1–2**
- ✅ AWS infrastructure (Terraform) — written, not yet applied
- ✅ TimescaleDB schema (10 tables + hypertables)
- ✅ Async DB client (TimescaleClient) — 8/8 tests passing
- ✅ Folder structure created
- ✅ requirements.txt installed
- ✅ config/settings.py with env vars
- ✅ Core agent framework (agent_base, registry, messaging, orchestrator)
- ✅ L1 Data ingestion agents (EquityIngestor, CryptoIngestor)
- ✅ Feature engineering pipeline (technical, microstructure, regime)

**Milestone 1 is DONE when:** running `python -m atlas.core.meta_orchestrator`
shows real market data flowing into TimescaleDB with features computing.

### Milestone 2 — Core Agent Layers (L2–L5) — $1,000
**Days 3–4**
- ✅ L2: IdeatorAgent ×5 (Claude API strategy generation)
- ✅ L2: CoderAgent (strategy spec → Python code via Claude)
- ✅ L2: CombinerAgent (hybrid strategies)
- ✅ L2: MutatorAgent (parameter optimization)
- ✅ L3: BacktestRunner ×2 (with L2 execution model)
- ✅ L3: ValidationAgents (7 tests: Sharpe, drawdown, overfitting, etc.)
- ✅ L4: RiskControllers + KillSwitch (FastAPI + Redis/DB persistence)
- ✅ L5: Paper execution on Alpaca + Binance (fully operational)

### Milestone 3 — Intelligence + Dashboard — $1,000
**Days 5–7**
- ⏳ Self-improvement loop (fully coded)
- ⏳ Meta-Orchestrator fully operational
- ⏳ 20–30 strategies processed end-to-end
- ✅ Dashboard REST APIs (all endpoints live on port 8080)
- ✅ WebSocket feeds (live Redis stream multiplexing)
- ⏳ Daily Intelligence Brief auto-generation
- ⏳ Full documentation

---

## 4. TECH STACK

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Cloud | AWS (EC2 t3.xlarge, RDS PostgreSQL 15, ElastiCache Redis, S3) |
| Database | TimescaleDB (time-series extension on PostgreSQL) |
| Cache/Messaging | Redis (pub/sub + heartbeats) |
| Equities Data | Polygon.io WebSocket (Level 2 + order flow) |
| Crypto Data | Binance WebSocket (@trade, @depth20@100ms) |
| AI Brain | Anthropic Claude API (claude-sonnet-4-20250514) |
| Paper Trading | Alpaca (equities), Binance (crypto) |
| Forex | OANDA (Phase 2) |
| API Framework | FastAPI + uvicorn |
| Logging | Loguru |
| Data Models | Pydantic v2 |
| Testing | pytest + pytest-asyncio |
| IaC | Terraform |
| Package Manager | pip |
| IDE | VS Code + GitHub Copilot + Antigravity (Google agent IDE) |

---

## 5. PROJECT STRUCTURE

```
C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS\
├── atlas/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent_base.py          # Abstract BaseAgent class
│   │   ├── agent_registry.py      # Register/deregister/health check
│   │   ├── messaging.py           # Redis pub/sub wrapper
│   │   └── meta_orchestrator.py   # Spawns/monitors all agents
│   ├── data/
│   │   ├── __init__.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── polygon_client.py  # Polygon.io WebSocket client
│   │   │   ├── binance_client.py  # Binance WebSocket client
│   │   │   └── data_normalizer.py # Normalize feeds → standard models
│   │   ├── features/
│   │   │   ├── __init__.py
│   │   │   ├── feature_engine.py  # ✅ DONE — Master feature orchestrator
│   │   │   ├── technical.py       # ✅ DONE — RSI, MACD, Bollinger, ATR, VWAP etc.
│   │   │   ├── microstructure.py  # ✅ DONE — Bid-ask, order imbalance, flow
│   │   │   └── regime.py          # ✅ DONE — Market regime detection
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── schema.sql         # ✅ DONE — TimescaleDB schema
│   │       └── timescale_client.py # ✅ DONE — async DB client (Extended for L3/L4)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── l1_data/
│   │   │   ├── __init__.py
│   │   │   ├── equity_ingestor.py # EquityIngestorAgent
│   │   │   ├── crypto_ingestor.py # CryptoIngestorAgent
│   │   │   └── feature_agent.py   # FeatureAgent
│   │   ├── l2_strategy/
│   │   │   ├── __init__.py
│   │   │   ├── strategy_base.py   # StrategyBase abstract class
│   │   │   ├── ideator_agent.py   # IdeatorAgent ×5 (Claude API)
│   │   │   ├── coder_agent.py     # CoderAgent (spec → Python)
│   │   │   ├── combiner_agent.py  # CombinerAgent (hybrid strategies)
│   │   │   └── mutator_agent.py   # MutatorAgent (parameter optimization)
│   │   ├── l3_backtest/
│   │   │   ├── __init__.py
│   │   │   ├── backtest_runner.py # ✅ DONE — Multi-split vectorized backtester
│   │   │   └── validator_agent.py # ✅ DONE — 7-step statistical validator
│   │   ├── l4_risk/
│   │   │   ├── __init__.py
│   │   │   ├── risk_controller.py # ✅ DONE — Position/drawdown/exposure limits
│   │   │   └── kill_switch.py     # ✅ DONE — Emergency halt (FastAPI + Persistence)
│   │   └── l5_execution/
│   │       ├── __init__.py
│   │       ├── alpaca_executor.py # ✅ DONE — Alpaca paper execution
│   │       └── binance_executor.py# ✅ DONE — Binance paper execution
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # ✅ DONE — pydantic-settings env loader
│   │   └── .env.example           # ✅ DONE — all API key placeholders
│   └── tests/
│       ├── __init__.py
│       ├── test_db.py             # ✅ DONE — 8/8 passing
│       ├── test_ingestion.py      # ✅ DONE — 11/11 passing
│       ├── test_agent_base.py     # ✅ DONE — 5/5 passing
│       ├── test_features.py       # ✅ DONE — 4/4 passing
│       ├── test_l2_agents.py      # ✅ DONE — 6/6 passing
│       ├── test_l4_risk.py        # ✅ DONE — 6/6 passing
│       ├── test_l5_execution.py    # ✅ DONE — 5/5 passing
│       └── test_l3_backtest.py    # ✅ DONE — 5/5 passing
├── infrastructure/
│   └── terraform/
│       ├── main.tf                # ✅ DONE — AWS provisioning
│       ├── variables.tf
│       └── outputs.tf
├── conftest.py                    # ✅ sys.path fix for pytest
├── pyproject.toml                 # ✅ package config (UTF-8 no BOM)
└── requirements.txt               # ✅ all packages installed
```

---

## 6. DATABASE SCHEMA (TimescaleDB)

All tables live in TimescaleDB on AWS RDS PostgreSQL 15.

| Table | Type | Purpose |
|---|---|---|
| market_data_l1 | hypertable | OHLCV bars from Polygon + Binance |
| market_data_l2 | hypertable | Order book snapshots (bids/asks) |
| order_flow | hypertable | Individual trade prints |
| features | hypertable | All computed features per symbol |
| strategies | standard | Strategy registry (spec + code + status) |
| backtest_results | standard | All backtest runs + validation results |
| paper_trades | hypertable | Paper trade fills + P&L |
| agent_registry | standard | All agents: status, heartbeat, metadata |
| system_logs | hypertable | All agent logs |
| performance_metrics | hypertable | Live strategy performance tracking |
| intelligence_briefs | standard | Daily generated AI intelligence briefs |

**Strategy status flow:**
`pending_code` → `pending_backtest` → `validated` → `paper_trading` → `promoted`

---

## 7. AGENT ARCHITECTURE

### Redis Channels (pub/sub messaging)
| Channel | Publisher | Subscriber |
|---|---|---|
| market_data | L1 agents | Feature engine |
| strategy_signals | Feature engine | L2 Ideators |
| risk_alerts | L4 Risk | L5 Execution, Orchestrator |
| execution_fills | L5 Execution | Performance tracker |
| system_events | All agents | Meta-Orchestrator |

### Agent Heartbeat System
- Every agent writes to Redis: `HSET agent:{id} status layer name` every 10s
- TTL = 30 seconds
- Meta-Orchestrator polls every 30s
- If heartbeat gap > 30s → restart agent → Slack alert → log to system_logs
- Max 3 auto-restart attempts with exponential backoff

### Startup Order (meta_orchestrator.py)
1. EquityIngestorAgent + CryptoIngestorAgent (parallel)
2. FeatureAgent (5s delay, after data agents confirm running)
3. IdeatorAgent ×5 (after FeatureAgent confirms running)
4. CoderAgent, CombinerAgent, MutatorAgent (after Ideators)
5. BacktestRunner ×2, ValidationAgent (continuous)
6. RiskController, KillSwitch (always on)
7. AlpacaExecutor, BinanceExecutor (paper mode)

---

## 8. CLAUDE API INTEGRATION (L2 Strategy Layer)

**Model:** `claude-sonnet-4-20250514`
**Library:** `anthropic` Python package
**API Key:** from `config/settings.py` → `ANTHROPIC_API_KEY`

### IdeatorAgent — generates strategy specs
- Runs every 5 minutes or after 10 new signals
- Reads feature snapshot + last 5 backtest results from DB
- Calls Claude with dynamic prompt including market conditions
- Parses JSON response → saves to strategies table
- 5 instances run in parallel with temperatures: 0.7, 0.8, 0.9, 1.0, 1.1
- Claude returns structured JSON: name, hypothesis, entry/exit conditions,
  stop_loss, take_profit, timeframe, asset_class, expected_sharpe, tags

### CoderAgent — converts specs to executable Python
- Listens for "new_spec" events on Redis
- Calls Claude to convert strategy JSON → Python class inheriting StrategyBase
- Generated class must implement: `generate_signals(df) -> pd.Series`
  returning 1 (buy), -1 (sell), 0 (hold)
- Runs syntax check on generated code
- If syntax error → sends back to Claude with error for self-correction (max 2x)
- Saves code to strategies table (status → "pending_backtest")

### CombinerAgent — creates hybrid strategies
- Runs every 2 hours
- Fetches top 5 validated strategies by Sharpe ratio
- Picks 2, asks Claude to combine them into a superior hybrid

### MutatorAgent — optimizes parameters
- Runs every 3 hours
- Targets strategies with Sharpe 1.0–2.0 (improvement candidates)
- Asks Claude to suggest parameter mutations

### Error Handling (all L2 agents)
- Malformed JSON from Claude → retry up to 3 times with rephrased prompt
- API failure → exponential backoff, max 5 retries
- Log every Claude call: tokens used, latency, success/fail

---

## 9. FEATURE ENGINEERING (50+ features)

### Technical Features (technical.py) — from OHLCV DataFrame
RSI(7,14,21), MACD(12,26,9), Bollinger Bands(20,2) with %B + bandwidth,
ATR(7,14), VWAP + deviation, EMA(9,21,50,200), SMA(20,50),
Stochastic %K/%D(14,3,3), Williams %R(14), CCI(20), ADX(14) +DI -DI,
OBV + slope, Volume ratio, ROC(10,20), Keltner Channel(20,2),
Donchian Channel(20), Parabolic SAR

### Microstructure Features (microstructure.py) — from L2 order book
bid_ask_spread_abs, bid_ask_spread_rel, order_book_imbalance (top 5),
trade_flow_imbalance (rolling 1min), large_trade_flag, tick_direction,
price_impact_estimate

### Regime Features (regime.py)
volatility_regime (low/medium/high), trend_regime (trending/ranging),
volume_regime (low/normal/high), market_session (pre/regular/after/overnight)

**Library:** `ta` package only — NOT TA-Lib (not installed on Windows)
**Rule:** All features return None on insufficient data — never raise exceptions

---

## 10. ENVIRONMENT VARIABLES NEEDED (.env file)

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/atlas
REDIS_URL=redis://host:6379
POLYGON_API_KEY=your_key_here
BINANCE_API_KEY=your_key_here
BINANCE_SECRET=your_secret_here
ANTHROPIC_API_KEY=your_key_here
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
SLACK_WEBHOOK_URL=your_webhook_here
WATCHLIST=SPY,QQQ,AAPL,TSLA,NVDA,MSFT,AMZN,META,GOOGL,AMD
CRYPTO_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
ENVIRONMENT=dev
```

---

## 11. CURRENT STATUS (End of Day 2 Morning)

### ✅ DONE
- [x] Folder structure + all `__init__.py` files created
- [x] `conftest.py` + `pyproject.toml` created (UTF-8 no BOM)
- [x] `pip install -e .` — atlas importable as package
- [x] `requirements.txt` — all packages installed
- [x] `config/settings.py` — pydantic-settings env loader
- [x] `config/.env.example` — all placeholders
- [x] `data/storage/schema.sql` — 10 tables + hypertables
- [x] `data/storage/timescale_client.py` — async DB client
- [x] `tests/test_db.py` — 8/8 tests passing
- [x] `infrastructure/terraform/main.tf` — AWS ready to apply
- [x] `import atlas` prints OK in terminal
- [x] Feature engineering pipeline (technical, microstructure, regime, engine)
- [x] `tests/test_features.py` — 4/4 tests passing

### ⏳ IN PROGRESS (Day 2 tasks)
- [x] `core/agent_base.py`
- [x] `core/agent_registry.py`
- [x] `core/messaging.py`
- [x] `core/meta_orchestrator.py`
- [x] `tests/test_agent_base.py`
- [x] `data/ingestion/polygon_client.py`
- [x] `data/ingestion/binance_client.py`
- [x] `data/ingestion/data_normalizer.py`
- [x] `tests/test_ingestion.py`
- [ ] L1 agent wrappers (equity_ingestor, crypto_ingestor, feature_agent) — Framework done, specific wrappers pending

### ✅ L2 STRATEGY LAYER (Completed)
- [x] L2 strategy agents (ideator, coder, combiner, mutator) implemented with Claude API
- [x] `tests/test_l2_agents.py` — 6/6 tests passing
- [x] `anthropic_api_key` added to settings
- [x] `timescale_client.py` extended with new db methods

### ✅ L4 RISK MANAGEMENT LAYER (Completed)
- [x] `risk_controller.py` — Daily/Weekly loss tracking + Trade approval logic
- [x] `kill_switch.py` — Dual-persistence (Redis + DB) + FastAPI Admin API (Port 8001)
- [x] `tests/test_l4_risk.py` — 6/6 tests passing
- [x] `timescale_client.py` extended with PnL and Metadata methods

### ✅ L7 META LAYER (Completed)
- [x] Self-improvement loop (`self_improvement_agent.py`)
- [x] Daily Intelligence Brief (`intelligence_brief_agent.py`)
- [x] `tests/test_l7_meta.py` — 4/4 tests passing
- [x] `intelligence_briefs` table added to schema

### ✅ L5 PAPER EXECUTION LAYER (Completed)
- [x] `alpaca_executor.py` — REST API integration + fill polling
- [x] `binance_executor.py` — Testnet integration + HMAC signing + precision rounding
- [x] `tests/test_l5_execution.py` — 5/5 tests passing

### ✅ DASHBOARD & API (Completed)
- [x] `api/main.py` — FastAPI server on port 8080
- [x] WebSocket implementation for live Redis data forwarding
- [x] All 11+ endpoints implemented (Health, Portfolio, Risk, etc.)

### ✅ L3 BACKTESTING LAYER (Completed)
- [x] `backtest_runner.py` — Vectorized engine with slippage, commissions, and 60/20/20 train/test/holdout split
- [x] `validator_agent.py` — 7 validation tests (Sharpe, DD, trades, win rate, PF, t-test, overfitting)
- [x] `tests/test_l3_backtest.py` — 5/5 tests passing
- [x] `timescale_client.py` extended with `save_backtest_results`

### 🔴 NOT STARTED YET
- [ ] L1 agent wrappers (equity_ingestor, crypto_ingestor, feature_agent) — Framework done, specific wrappers pending
- [ ] Integration: End-to-end flow from Ideator -> Backtester -> Validator -> Executor

---

## 12. KNOWN ISSUES & FIXES APPLIED

| Issue | Fix Applied |
|---|---|
| `ModuleNotFoundError: No module named 'atlas'` | Added `__init__.py` to all folders + `conftest.py` + `pip install -e .` |
| `type nul >` fails in PowerShell | Used `New-Item -ItemType File` instead |
| `pyproject.toml` BOM encoding error | Used `[System.IO.File]::WriteAllText` with UTF8 no BOM |
| `pytest` must run from root dir | Always: `cd C:\Pranith\...\05-11-2026-Amit-ATLAS` then `pytest atlas/tests/ -v` |
| `fakeredis` missing in tests | Fixed by mocking `KillSwitch.is_active` with `AsyncMock` to decouple from Redis |
| `RiskController` instance error | Fixed `TypeError` by properly instantiating `RiskController` in executors rather than calling class methods |
| `ModuleNotFoundError: asyncpg` in tests | Mocked `TimescaleClient` in tests to decouple from DB drivers during unit testing |
| `ANTHROPIC_API_KEY` missing in tests | Mocked `get_settings` in test fixtures to provide dummy API keys for validation |

---

## 13. TOOLS BEING USED

| Tool | Purpose |
|---|---|
| **Antigravity** | Google's agent IDE — runs 3 parallel AI agents for large code generation tasks |
| **VS Code + GitHub Copilot** | Inline code refinement, bug fixing, reviewing Antigravity output |
| **PowerShell** | Terminal (NOT Command Prompt — syntax differs) |
| **pytest** | Always run from ROOT directory |

### Antigravity Strategy
- Agent 1 = Infrastructure tasks
- Agent 2 = Core logic / AI layer
- Agent 3 = Framework / base classes
- Let agents run in parallel, then use Copilot to review + fix output
- Set: Terminal execution AUTO, File write = Review before saving

---

## 14. DAY-BY-DAY PLAN

| Day | Milestone | Key Deliverables |
|---|---|---|
| 1 | M1 foundation | Folder structure, DB schema, Terraform, settings ✅ |
| 2 | M1 completion | Core agents, data ingestion, feature engine, L2 agents start |
| 3 | M2 start | L2 agents complete, L3 backtesting + validation |
| 4 | M2 completion | L4 risk + kill switch, L5 paper execution, end-to-end test |
| 5–7 | M3 | Self-improvement, dashboard APIs, 20-30 strategies, docs |

---

## 15. HOW TO RESUME THIS PROJECT (if starting fresh)

1. Read sections 2–5 to understand scope and structure
2. Check section 11 (Current Status) to see what's done
3. Run `pytest atlas/tests/ -v` from root to verify what's working
4. Pick up from the first ⏳ item in section 11
5. Use the Antigravity prompts from the conversation for each layer
6. Always run pytest after each Antigravity session to confirm no regressions
7. Update this file's section 11 as tasks complete

---

## 16. NEXT PROMPT TO RUN (Day 2 — after core framework tests pass)

Feed this to **Antigravity Agent 1** for the Feature Engineering layer:

> See Day 2 — Step 2 prompt in conversation (Feature Engineering: technical.py,
> microstructure.py, regime.py, feature_engine.py with 50+ features)

Feed this to **Antigravity Agent 2** for L2 Strategy Agents:

> See Day 2 — Step 3 prompt in conversation (L2 agents: ideator, coder,
> combiner, mutator — all using Claude API claude-sonnet-4-20250514)

---

*This file should be updated at the end of each day.*
*Keep it in the root of the project: `05-11-2026-Amit-ATLAS/ATLAS_PROJECT_MEMORY.md`*
