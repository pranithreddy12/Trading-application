# ATLAS Setup & Deployment Guide

**Version:** 1.0.0  
**Last Updated:** May 2026

---

## 1. Prerequisites

| Component | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Runtime |
| PostgreSQL | ≥ 14 | Relational database |
| TimescaleDB | ≥ 2.10 | Time-series extension on PostgreSQL |
| Redis | ≥ 7.0 | Pub/sub messaging + state |
| Git | ≥ 2.30 | Version control |
| Docker (optional) | ≥ 24.0 | Containerized deployment |

### Required Python Packages

All dependencies are listed in `requirements.txt` at the project root. Key packages:

| Package | Purpose |
|---|---|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `sqlalchemy` | Database ORM |
| `redis` | Pub/sub + caching |
| `loguru` | Structured logging |
| `httpx` | Async HTTP client |
| `pandas` | Data analysis |
| `numpy` | Numerical computation |
| `alpaca-py` | Broker integration |

Install with:

```bash
pip install -r requirements.txt
```

---

## 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/atlas

# Redis
REDIS_URL=redis://localhost:6379/0

# Environment (dev | staging | production)
ENVIRONMENT=dev

# Logging
LOG_LEVEL=INFO

# Strategy Pipeline
MAX_STRATEGIES_PER_CYCLE=5
STRATEGY_COOLDOWN_SECONDS=60

# Claude API (for ideator)
CLAUDE_API_KEY=sk-ant-...

# Broker API (for live execution)
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Scout API Keys (external signals)
TWITTER_BEARER_TOKEN=...
NEWS_API_KEY=...
```

---

## 3. Database Setup

### 3.1 Install TimescaleDB

```bash
# Ubuntu/Debian
sudo apt install timescaledb-2-postgresql-14
sudo timescaledb-tune
sudo systemctl restart postgresql

# macOS (Homebrew)
brew install timescaledb
brew services restart postgresql

# Windows (Docker recommended)
docker run -d --name atlas-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=atlas \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg14
```

### 3.2 Initialize Schema

Run the database schema migration:

```bash
python scripts/reset_and_recode.py
```

Or for a fresh deployment:

```bash
python -c "
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
import asyncio

async def init():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    await db.create_all_tables()
    print('Schema initialized')

asyncio.run(init())
"
```

### 3.3 Seed Historical Data (Optional)

For backtesting:

```bash
python scripts/seed_historical_data.py
```

This loads minutely OHLCV data for common crypto and equity symbols into TimescaleDB hypertables.

---

## 4. Redis Setup

### 4.1 Install

```bash
# Ubuntu/Debian
sudo apt install redis-server

# macOS
brew install redis

# Windows
docker run -d --name atlas-redis -p 6379:6379 redis:7-alpine
```

### 4.2 Verify

```bash
redis-cli ping
# Should respond: PONG
```

---

## 5. Running the System

### 5.1 Start Core Services

```bash
# Terminal 1: Redis (if running locally)
redis-server

# Terminal 2: API Server
python -m atlas.api.main

# Terminal 3: Pipeline
python scripts/run_pipeline.py

# Terminal 4: Execution Gateway
python scripts/run_execution_chain.py
```

### 5.2 Verify Services

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "ok",
#   "agents_alive": 5,
#   "agents_dead": 0,
#   "kill_switch_active": false,
#   "components": {
#     "database": "healthy",
#     "redis": "healthy",
#     "api": "healthy"
#   }
# }
```

### 5.3 Dashboard

Open in browser:

```
http://localhost:8000/dashboard
```

The dashboard provides:
- System overview (strategy counts, backtest volume, pipeline stats)
- Pipeline tracking (strategy lifecycle funnel)
- Risk overview (kill switch, drawdown, copy trader status)
- Portfolio view (allocation, diversification, ensemble trades)
- Pattern intelligence (top patterns with confidence scores)
- Live traces (recent lifecycle events)
- Scout signals (external intelligence sources)
- Validation analysis (walk-forward, Monte Carlo, overfitting)

---

## 6. Individual Component Startup

Each agent can be started independently:

```bash
# Strategy Ideation
python -c "from atlas.agents.l2_strategy.ideator_agent_v2 import IdeatorAgentV2; ..."

# Backtesting
python -m atlas.agents.l3_backtest.backtest_runner

# Validation
python -m atlas.agents.l3_backtest.validator_agent

# Execution
python scripts/run_execution_chain.py

# Portfolio Intelligence
python -m atlas.agents.l6_portfolio.portfolio_intelligence_engine

# Meta Intelligence
python -m atlas.agents.l7_meta.meta_reasoning_agent
```

---

## 7. Running Tests

### 7.1 Full Test Suite

```bash
cd atlas
python -m pytest tests/ -v --tb=short
```

Expected result: **193 tests passing, 0 failures**.

### 7.2 Test Categories

| Test File | Coverage |
|---|---|
| `tests/test_agent_base.py` | Agent lifecycle, heartbeat, messaging |
| `tests/test_l2_agents.py` | Ideator, coder, strategy normalizer |
| `tests/test_l3_backtest.py` | Backtest runner, validator, slippage |
| `tests/test_l4_risk.py` | Risk controller, kill switch |
| `tests/test_l5_execution.py` | Execution gateway, order tracking |
| `tests/test_l7_meta.py` | Meta agents, mutation policy |
| `tests/test_db.py` | Database operations |
| `tests/test_features.py` | Feature extraction and normalization |
| `tests/test_ingestion.py` | Data ingestion pipeline |
| `tests/test_internal_scout_network.py` | Scout signal validation |
| `tests/chaos/test_scout_corruption.py` | Malformed signal rejection |

### 7.3 Running Individual Tests

```bash
# Single test
python -m pytest tests/test_l3_backtest.py::test_validator_passes_good_strategy -v

# All tests in a file
python -m pytest tests/test_l5_execution.py -v --tb=long

# With coverage
pip install pytest-cov
python -m pytest tests/ --cov=atlas --cov-report=term-missing
```

---

## 8. Soak Testing

Economic intelligence soaks demonstrate persistent adaptive behavior:

### 6-Hour Soak

```bash
python scripts/phase28_economic_soak.py --duration 6h --mode economic
```

### 12-Hour Soak

```bash
python scripts/phase28_economic_soak.py --duration 12h --mode economic
```

### Soak Monitoring

```bash
# Watch live metrics
curl http://localhost:8000/dashboard/api/overview

# Check for anomalies
curl http://localhost:8000/dashboard/api/observability/anomalies
```

---

## 9. Docker Deployment

### 9.1 Docker Compose

```yaml
version: "3.8"
services:
  db:
    image: timescale/timescaledb:latest-pg14
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: atlas
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    command: python -m atlas.api.main
    ports:
      - "8000:8000"
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/atlas
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: ${ENVIRONMENT}

  pipeline:
    build: .
    command: python scripts/run_pipeline.py
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/atlas
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: ${ENVIRONMENT}

volumes:
  pgdata:
```

### 9.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "atlas.api.main"]
```

---

## 10. Deployment Checklist

### Pre-Deployment

- [ ] All 193 tests pass
- [ ] Environment variables configured (not defaults)
- [ ] Database schema migrated
- [ ] Redis running
- [ ] Historical data seeded (if backtesting needed)
- [ ] API keys configured for Claude, Alpaca, and scouts
- [ ] Environment set to `production` (enables institutional validation rules)
- [ ] Kill switch verified operational
- [ ] Monitoring fabric started

### Health Verification

```bash
# API health
curl http://localhost:8000/health

# Database connectivity (from API)
curl http://localhost:8000/health | jq .components

# Agent heartbeat check
curl http://localhost:8000/control/agent-status

# Copy trading status
curl http://localhost:8000/copy/status
```

---

## 11. Troubleshooting

| Issue | Likely Cause | Solution |
|---|---|---|
| `Connection refused: localhost:5432` | PostgreSQL not running | `sudo systemctl start postgresql` |
| `Redis connection error` | Redis not running | `redis-server` |
| `ModuleNotFoundError: atlas.*` | Wrong working directory or package not installed | Run from project root or `pip install -e .` |
| `asyncpg.exceptions.InvalidAuthorizationSpecificationError` | Wrong database credentials | Check `.env` file |
| `Backtest returns 0 total_trades` | No signals generated | Check strategy code or market data availability |
| `Validator rejecting all strategies` | Environment set to `production` without good strategies | Set `ENVIRONMENT=dev` for development |
| `LLM API errors in ideator` | Invalid or expired Claude API key | Check `CLAUDE_API_KEY` |
| `Kill switch active` | Emergency stop triggered | `POST /kill_switch/deactivate` |

---

## 12. Architecture at a Glance

```
atlas/                          # Python package root
├── api/                        # FastAPI REST layer
├── agents/                     # Agent implementations (L1-L7)
├── core/                       # Foundation: base agent, messaging, CLI
├── config/                     # Centralized settings
├── data/                       # DB client, storage layer
├── dashboard/                  # Operator UI + control plane
├── observability/              # Monitoring fabric + anomaly detection
├── docs/                       # Documentation
├── scripts/                    # Run scripts, soaks, utilities
├── tests/                      # Test suite (193 tests)
├── requirements.txt
└── .env                        # Environment configuration
```
