# ATLAS Local Dev Environment — Verification Checklist

## Pre-flight Checks

- [ ] Docker Desktop is installed and **running** (whale icon in taskbar)
- [ ] No existing PostgreSQL on port 5432 (e.g., local pgAdmin installation)
- [ ] No existing Redis on port 6379
- [ ] Python 3.11 is active: `python --version`
- [ ] You are in the project root: `C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS`

---

## Quick Start Commands

```powershell
# From project root — run these in order:
cd C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS

# 1. Start services
docker-compose up -d

# 2. Run full setup + tests
.\setup_local_env.ps1
```

---

## Manual Verification Steps

### 1. TimescaleDB
```powershell
# Is it running?
docker ps | Select-String "atlas_timescaledb"

# Can you connect?
docker exec atlas_timescaledb pg_isready -U postgres -d atlas

# Is TimescaleDB extension active?
docker exec atlas_timescaledb psql -U postgres -d atlas -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"

# List all ATLAS tables
docker exec atlas_timescaledb psql -U postgres -d atlas -c "\dt"
```

**Expected output:** `timescaledb | X.X.X` and all 11 tables listed.

---

### 2. Redis
```powershell
# Is it running?
docker ps | Select-String "atlas_redis"

# Ping test
docker exec atlas_redis redis-cli ping
# Expected: PONG

# Check persistence
docker exec atlas_redis redis-cli config get appendonly
# Expected: appendonly → yes
```

---

### 3. Python / ATLAS Package
```powershell
# Verify import
python -c "import atlas; print('atlas import OK')"

# Run full test suite
$env:PYTHONPATH = "C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS"
pytest atlas/tests/ -v
```

**Expected:** All existing tests pass (test_db, test_agent_base, test_features, test_l2_agents, test_l4_risk, test_l7_meta)

---

## Troubleshooting

| Symptom | Command to Diagnose | Fix |
|---|---|---|
| DB not starting | `docker logs atlas_timescaledb --tail 50` | Check for port 5432 conflict |
| Redis not starting | `docker logs atlas_redis --tail 20` | Check for port 6379 conflict |
| Port in use | `Get-NetTCPConnection -LocalPort 5432` | Stop conflicting process or change port |
| Schema not loaded | `docker exec atlas_timescaledb psql -U postgres -d atlas -c "\dt"` | Check that `schema.sql` is mounted in docker-compose.yml |
| `import atlas` fails | `pip install -e .` from project root | Reinstall editable package |
| pytest can't find tests | Run from `C:\Pranith\...\05-11-2026-Amit-ATLAS` | Always run pytest from project root |
| TimescaleDB extension missing | Check `init_timescale.sql` is at `atlas/data/storage/init_timescale.sql` | Wipe volumes: `docker-compose down -v && docker-compose up -d` |

---

## Service Management

```powershell
# Start
docker-compose up -d

# Stop (keeps data)
docker-compose down

# Stop + wipe all data (fresh start)
docker-compose down -v

# View logs
docker logs atlas_timescaledb -f
docker logs atlas_redis -f

# Container shell access
docker exec -it atlas_timescaledb bash
docker exec -it atlas_redis sh
```

---

## Current Test Suite Status (Day 3)

| Test File | Tests | Status |
|---|---|---|
| `test_db.py` | 8 | ✅ Passing |
| `test_agent_base.py` | 5 | ✅ Passing |
| `test_features.py` | 4 | ✅ Passing |
| `test_ingestion.py` | 11 | ✅ Passing |
| `test_l2_agents.py` | 6 | ✅ Passing |
| `test_l4_risk.py` | 6 | ✅ Passing |
| `test_l7_meta.py` | 4 | ✅ Passing |
| **Total** | **44** | ✅ All passing |

---

## Environment Variable Reference

| Variable | Value (local dev) | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5432/atlas` | From docker-compose |
| `REDIS_URL` | `redis://localhost:6379` | From docker-compose |
| `ENVIRONMENT` | `dev` | Controls behavior flags |
| `POLYGON_API_KEY` | `your_key_here` | Required for live equity data |
| `BINANCE_API_KEY` | `your_key_here` | Required for live crypto data |
| `ANTHROPIC_API_KEY` | `your_key_here` | Required for L2 Claude agents |
| `ALPACA_API_KEY` | `your_key_here` | Required for paper trading |
