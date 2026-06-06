# ATLAS — Setup & Deployment Guide

## Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+** with TimescaleDB extension
- **Redis 7+**
- **Docker** (optional, for containerized deployment)

## Quick Start (Local Development)

```bash
# 1. Clone the repository
git clone <repo-url>
cd atlas

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r atlas/requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your database credentials, API keys, etc.

# 5. Start infrastructure
docker compose up -d postgres redis  # or use local instances

# 6. Run database migrations
python scripts/run_migration.py

# 7. Verify setup
python verify_setup.py
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL/TimescaleDB connection | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |
| `BINANCE_API_KEY` | Binance exchange API key | — |
| `ALPACA_API_KEY` | Alpaca exchange API key | — |
| `POLYGON_API_KEY` | Polygon market data API key | — |

## Running the System

```bash
# Start the FastAPI server
uvicorn atlas.api.main:app --reload --port 8000

# Run a coverage demo
python scripts/phase34_coverage_demo.py --duration-minutes 30

# Run the meta orchestrator (full autonomous mode)
python -c "from atlas.core.meta_orchestrator import run; run()"

# Run a benchmark soak
python scripts/phase33_performance_benchmark_soak.py --duration-minutes 60
```

## Docker Deployment

```bash
# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f api

# Scale agents
docker compose up -d --scale mutator=3
```

## Testing

```bash
# Run all tests
pytest atlas/tests/ -v

# Run specific test suite
pytest atlas/tests/test_l7_meta.py -v

# Run coverage soak
python scripts/phase34_coverage_demo.py --duration-minutes 15
```

## Verification Checklist

- [ ] Database connects and migrations applied
- [ ] Redis connects and pub/sub works
- [ ] API server responds on port 8000
- [ ] Replay integrity check passes
- [ ] At least one mutation cycle completes
- [ ] Audit ledger entries are written
- [ ] Dashboard loads at `/dashboard/`
