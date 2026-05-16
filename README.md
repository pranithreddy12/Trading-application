# ATLAS — Automated Trading & Learning Agent System

ATLAS is an AI-powered quantitative trading framework that generates, codes, backtests, and validates trading strategies using Claude (Anthropic) for strategy ideation. Designed for 1-minute intraday equities and crypto markets.

## Architecture

```
L1 Data Ingestors ──► Feature Pipeline ──► L2 Ideator Agents (x5)
                                              │
                                              ▼
                                         Coder Agent
                                              │
                                              ▼
                                      L3 Backtest Runner
                                              │
                                              ▼
                                       Validator Agent
                                              │
                                         ┌────┴────┐
                                         ▼         ▼
                                    Mutator    Combiner
```

### Layers

| Layer | Component | Description |
|-------|-----------|-------------|
| L1 | EquityIngestor / CryptoIngestor | Real-time market data ingestion |
| L1 | FeatureAgent | Technical indicator computation (RSI, MACD, Bollinger, VWAP, etc.) |
| L2 | IdeatorAgent (x5) | Claude-powered strategy generation with archetype specialization |
| L2 | CoderAgent | Auto-compiles strategy specs into executable Python |
| L2 | MutatorAgent | Evolves borderline strategies via deterministic + Claude mutations |
| L2 | CombinerAgent | Hybridizes top-performing strategies |
| L3 | BacktestRunner | 1-minute bar backtesting engine |
| L3 | ValidatorAgent | Sharpe, drawdown, win-rate gates |

### 5 Ideator Agents — Specialized Research Desks

Each agent operates as a dedicated research desk with:
- Fixed archetype (Momentum, Mean Reversion, Breakout, Volatility, Trend)
- Archetype-specific feature whitelist
- Rotating feature subsets
- Temperature diversification (0.3–1.0)
- Content-based duplicate rejection (strategy signature hashing)

## Prerequisites

- Python 3.11+
- PostgreSQL (with TimescaleDB recommended)
- Redis
- Anthropic API key

## Setup

```bash
# Clone
git clone <repo-url>
cd atlas

# Environment
cp .env.example .env
# Edit .env with your keys

# Install
pip install -r atlas/requirements.txt

# Database
# Ensure PostgreSQL + Redis are running
python -c "from atlas.data.storage.timescale_client import TimescaleClient; print('DB configured')"
```

## Running

### Start all agents (production mode)

```bash
python -m atlas.core.meta_orchestrator
```

### Run end-to-end pipeline

```bash
python atlas/scripts/run_pipeline.py
```

### Run individual components

```bash
# Generate strategies
python -m atlas.agents.l2_strategy.ideator_agent

# Code pending strategies
python -m atlas.agents.l2_strategy.coder_agent

# Run backtests
python -m atlas.agents.l3_backtest.backtest_runner

# Validate results
python -m atlas.agents.l3_backtest.validator_agent
```

### Run tests

```bash
pytest atlas/tests/ -v
```

## Pipeline Flow

1. **Ideator** generates strategy specs via Claude (5 parallel agents)
2. **Coder** compiles specs into executable Python classes
3. **BacktestRunner** evaluates on historical 1-minute data
4. **Validator** assigns tiers: `validated_A`, `validated_B`, `research_candidate`, `failed_validation`
5. **Mutator** refines weak-but-viable strategies
6. **Combiner** creates hybrids from top performers

## Strategy Generation

Each Ideator agent receives a minimal prompt with:
- Asset class and archetype
- Archetype-specific allowed features
- Current rotating feature subset
- Market regime (bullish/bearish/neutral)
- Target 5–50 weekly entries
- Recently used feature combinations to avoid

Duplicate strategies are rejected by **content signature** (hash of entry/exit conditions + asset class), not by name.

## Project Structure

```
atlas/
├── agents/
│   ├── l1_ingestion/       # Market data ingestors
│   ├── l1_features/        # Feature engineering
│   ├── l2_strategy/        # Ideator, Coder, Mutator, Combiner
│   └── l3_backtest/        # Backtest runner, Validator
├── config/                 # Settings & configuration
├── core/                   # Base agent, orchestrator, messaging
├── data/
│   ├── features/           # Indicator implementations
│   └── storage/            # TimescaleDB client + schema
├── scripts/                # Pipeline, utility scripts
├── api/                    # FastAPI routes (scaffolded)
├── tests/                  # Agent tests
└── requirements.txt
```

## Known Limitations

- **L4/L5** (Risk management, Execution) — architecture defined, not yet deployed
- **Scout network** — peer discovery for signal sharing is future scope
- **Dashboard** — real-time monitoring UI is planned
- **Full API surface** — REST API routes are scaffolded but not hardened

See [ATLAS_Test_Status.md](ATLAS_Test_Status.md) for detailed capability mapping.
