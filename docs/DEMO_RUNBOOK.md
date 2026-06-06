# ATLAS Demo Runbook
## Complete Command Reference for Live Demonstrations

> **Generated:** June 1, 2026
> **Purpose:** Step-by-step commands to run every ATLAS layer, verify outputs, and monitor the live dashboard.
> **Platform:** Windows (PowerShell commands included alongside bash)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Infrastructure Health Checks](#2-infrastructure-health-checks)
3. [Database Migrations](#3-database-migrations)
4. [Seeding Data](#4-seeding-data)
5. [Running Each Layer Individually](#5-running-each-layer-individually)
6. [Running the Full Pipeline](#6-running-the-full-pipeline)
7. [Dashboard & API Endpoints](#7-dashboard--api-endpoints)
8. [DB Verification Queries](#8-db-verification-queries)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

### Environment Setup
```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Verify .env exists with required keys
cat .env
```

### Required Services
| Service | Default URL | Check Command |
|---------|-------------|---------------|
| **PostgreSQL/TimescaleDB** | `postgresql+asyncpg://postgres:password@localhost:5433/atlas` | `python -c "from atlas.data.storage.timescale_client import TimescaleClient; ..."` |
| **Redis** | `redis://localhost:6379` | `python -c "import asyncio; from redis.asyncio import Redis; r=Redis.from_url('redis://localhost:6379'); asyncio.run(r.ping()); print('OK')"` |

---

## 2. Infrastructure Health Checks

### Quick Connectivity Test
```bash
# Test DB + Redis + all core imports in one shot
python -c "
from atlas.core.agent_base import BaseAgent
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.core.messaging import MessagingClient
from atlas.core.selection import tournament_select
from atlas.api.main import app
print('All imports + API app: OK')
"
```

### FastAPI Health Endpoint
```bash
# Start API server (if not running)
python -m uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000 &

# Check health
curl http://localhost:8000/health
# Expected: {"status":"ok","components":{"database":"healthy","redis":"healthy","api":"healthy"}}
```

### Database Schema Validation
```bash
python -c "
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

async def check():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    print('DB connected — schema validated')
    await db.close()

asyncio.run(check())
"
```

---

## 3. Seeding Data

### Seed Historical Market Data (Equity)
```bash
python atlas/scripts/seed_equity_data.py
```
**Verify:**
```sql
SELECT COUNT(*) FROM market_data_l1;
SELECT DISTINCT symbol FROM market_data_l1 ORDER BY symbol;
```

### Seed Historical Features
```bash
python atlas/scripts/seed_historical_data.py
```
**Verify:**
```sql
SELECT COUNT(*) FROM features;
SELECT feature_name, COUNT(*) FROM features GROUP BY feature_name ORDER BY COUNT(*) DESC LIMIT 10;
```

### Seed Event Store & Audit Ledger
```bash
python atlas/scripts/seed_event_store_and_audit.py
```
**Verify:**
```sql
SELECT COUNT(*) FROM event_store;
SELECT COUNT(*) FROM audit_ledger;
```

---

## 4. Running Each Layer Individually

### Layer 1: Data Ingestion

#### L1a — Polygon REST (Equity Market Data)
```bash
# Runs as async agent within the full cycle, or standalone:
python -c "
import asyncio
from redis.asyncio import Redis
from atlas.agents.l1_data.polygon_rest_agent import PolygonRestAgent
from atlas.config.settings import settings

async def run():
    r = Redis.from_url(settings.redis_url)
    agent = PolygonRestAgent(r, settings.database_url)
    await agent.start()
    await asyncio.sleep(120)  # Run for 2 minutes
    await agent.stop()

asyncio.run(run())
"
```

### L1b — Binance WebSocket (Crypto Market Data)
> **Note:** Requires `BINANCE_API_KEY` and `BINANCE_SECRET` in `.env`. If not configured, the agent will be skipped during the full cycle.

**Verify market data ingestion:**
```sql
-- Check recent market data
SELECT symbol, time, open, high, low, close, volume
FROM market_data_l1
ORDER BY time DESC LIMIT 20;

-- Count by symbol
SELECT symbol, COUNT(*) as bars
FROM market_data_l1
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY symbol ORDER BY bars DESC;
```

#### L1b — Feature Engineering
```bash
# Feature agent runs within the full cycle
# Features are computed from raw market data
```

**Verify feature computation:**
```sql
-- Check feature computation status
SELECT feature_name, COUNT(DISTINCT symbol) as symbols, COUNT(*) as total_values
FROM features
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY feature_name
ORDER BY total_values DESC;

-- Check features_wide materialized view
SELECT * FROM features_wide LIMIT 5;
```

---

### Layer 2: Strategy Generation

#### L2a — IdeatorAgentV2 (Strategy Ideation)
```bash
# Runs within full cycle — generates strategy specs from templates + LLM
```

**Verify strategy generation:**
```sql
-- Strategy counts by status
SELECT status, COUNT(*) as cnt
FROM strategies
GROUP BY status ORDER BY cnt DESC;

-- Recent strategies
SELECT id, name, status, archetype, author_agent, created_at
FROM strategies
ORDER BY created_at DESC LIMIT 10;

-- Strategies by archetype
SELECT archetype, COUNT(*) as cnt
FROM strategies
GROUP BY archetype ORDER BY cnt DESC;

-- Strategies by regime
SELECT regime, COUNT(*) as cnt
FROM strategies
WHERE regime IS NOT NULL
GROUP BY regime ORDER BY cnt DESC;
```

#### L2b — CoderAgent (Code Generation)
```bash
# Generates executable Python code from strategy specs
```

**Verify code generation:**
```sql
-- Check code generation success rate
SELECT status, COUNT(*) as cnt
FROM strategies
WHERE code IS NOT NULL AND code != ''
GROUP BY status ORDER BY cnt DESC;

-- Check code_failed strategies
SELECT name, failure_reason
FROM strategies
WHERE status = 'code_failed'
ORDER BY created_at DESC LIMIT 5;
```

#### L2c — MutatorAgent (Strategy Mutation)
```bash
# Standalone run:
python atlas/scripts/run_mutator.py --cycles 5
```

**Verify mutations:**
```sql
-- Check mutation lineage
SELECT parent_id, COUNT(*) as children
FROM strategies
WHERE parent_id IS NOT NULL
GROUP BY parent_id ORDER BY children DESC LIMIT 10;

-- Check mutation memory
SELECT * FROM mutation_memory ORDER BY created_at DESC LIMIT 10;
```

#### L2d — CombinerAgent (Strategy Combination)
```bash
# Runs within full cycle — combines top strategies
```

**Verify combinations:**
```sql
-- Check combination memory
SELECT * FROM combination_memory ORDER BY created_at DESC LIMIT 10;

-- Combined strategies
SELECT name, parent_id, status
FROM strategies
WHERE combination_id IS NOT NULL
ORDER BY created_at DESC LIMIT 10;
```

---

### Layer 3: Backtesting

#### L3a — BacktestRunner
```bash
# Standalone run:
python atlas/scripts/run_pipeline.py
# Or within full cycle
```

**Verify backtest results:**
```sql
-- Backtest summary
SELECT COUNT(*) as total_backtests,
       AVG(short_window_score) as avg_score,
       MAX(short_window_score) as best_score
FROM backtest_results;

-- Recent backtest results
SELECT b.strategy_id, s.name, b.short_window_score,
       b.total_trades, b.win_rate, b.sharpe_ratio,
       b.max_drawdown, b.created_at
FROM backtest_results b
JOIN strategies s ON s.id = b.strategy_id
ORDER BY b.created_at DESC LIMIT 10;

-- Score distribution
SELECT
  CASE
    WHEN short_window_score >= 80 THEN '80+'
    WHEN short_window_score >= 60 THEN '60-79'
    WHEN short_window_score >= 40 THEN '40-59'
    WHEN short_window_score >= 20 THEN '20-39'
    ELSE '0-19'
  END as score_bucket,
  COUNT(*) as cnt
FROM backtest_results
GROUP BY score_bucket ORDER BY score_bucket DESC;
```

#### L3b — ValidatorAgent
```bash
# Standalone run:
python atlas/scripts/run_validator.py
```

**Verify validation results:**
```sql
-- Validation funnel
SELECT status, COUNT(*) as cnt
FROM strategies
WHERE status IN ('pending_validation', 'validated', 'elite',
                 'research_candidate', 'repair_candidate', 'failed_validation')
GROUP BY status ORDER BY cnt DESC;

-- Top validated strategies
SELECT s.name, s.status, s.archetype,
       b.short_window_score, b.win_rate, b.sharpe_ratio
FROM strategies s
JOIN backtest_results b ON b.strategy_id = s.id
WHERE s.status IN ('validated', 'elite')
ORDER BY b.short_window_score DESC LIMIT 10;

-- Pass rate
SELECT
  COUNT(*) FILTER (WHERE status IN ('validated', 'elite', 'research_candidate')) as passed,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status IN ('validated', 'elite', 'research_candidate')) / NULLIF(COUNT(*), 0), 1) as pass_rate_pct
FROM strategies;
```

#### L3c — Short Window Evaluator (Walk-Forward)
```bash
python atlas/scripts/run_walk_forward.py
```

**Verify walk-forward results:**
```sql
SELECT * FROM walk_forward_analysis ORDER BY analyzed_at DESC LIMIT 5;
```

---

### Layer 4: Risk Management

#### L4 — Risk Controllers
```bash
# Runs within full cycle
```

**Verify risk state:**
```sql
-- Kill switch status
SELECT * FROM risk_state;

-- Systemic risk
SELECT * FROM systemic_risk ORDER BY assessed_at DESC LIMIT 5;

-- Stress test results
SELECT * FROM stress_test_results ORDER BY tested_at DESC LIMIT 5;

-- Capital preservation
SELECT * FROM capital_preservation_state ORDER BY checked_at DESC LIMIT 5;
```

---

### Layer 5: Execution

#### L5a — ExecutionGateway (Paper Trading)
```bash
# Standalone test:
python atlas/scripts/run_execution_chain.py
```

**Verify execution:**
```sql
-- Paper trades
SELECT id, symbol, side, quantity, price, fill_price, status, pnl, time
FROM paper_trades
ORDER BY time DESC LIMIT 20;

-- Paper trade P&L
SELECT
  COUNT(*) as total_trades,
  COUNT(*) FILTER (WHERE pnl > 0) as winners,
  COUNT(*) FILTER (WHERE pnl < 0) as losers,
  COALESCE(SUM(pnl), 0) as total_pnl,
  COALESCE(AVG(pnl), 0) as avg_pnl
FROM paper_trades;

-- Execution log
SELECT order_key, strategy_id, symbol, side, quantity, price, state, created_at
FROM execution_log
ORDER BY created_at DESC LIMIT 20;

-- Dead letters (failed executions)
SELECT id, strategy_id, symbol, failure_reason, severity, retry_count
FROM execution_dead_letter
WHERE resolved = FALSE
ORDER BY severity DESC;
```

#### L5b — Copy Trader
```bash
python atlas/scripts/run_copy_trader_test.py
```

**Verify copy trading:**
```sql
SELECT * FROM copy_leader_accounts;
SELECT * FROM copy_follower_accounts;
SELECT * FROM copy_execution_log ORDER BY created_at DESC LIMIT 10;
```

---

### Layer 6: Portfolio Intelligence

#### L6 — Portfolio Intelligence & Capital Allocation
```bash
# Runs within full cycle
```

**Verify portfolio state:**
```sql
-- Portfolio intelligence
SELECT computed_at, n_strategies, diversification_score,
       concentration_risk, ensemble_survivability_score
FROM portfolio_intelligence ORDER BY computed_at DESC LIMIT 5;

-- Capital allocation
SELECT computed_at, method, total_exposure, n_strategies
FROM capital_allocation ORDER BY computed_at DESC LIMIT 5;

-- Ensemble execution
SELECT executed_at, n_signals_processed, n_trades_generated
FROM ensemble_execution ORDER BY executed_at DESC LIMIT 10;

-- Execution realism
SELECT simulated_at, n_trades_simulated, avg_fill_probability,
       avg_expected_slippage_bps
FROM execution_realism ORDER BY simulated_at DESC LIMIT 5;
```

---

### Layer 7: Meta-Intelligence

#### L7a — Replay Engine
```bash
# Runs within full cycle
```

**Verify replay integrity:**
```sql
-- Event store
SELECT COUNT(*) as total_events FROM event_store;
SELECT aggregate_type, event_type, COUNT(*) as cnt
FROM event_store GROUP BY aggregate_type, event_type ORDER BY cnt DESC;

-- Replay integrity
SELECT * FROM replay_integrity ORDER BY checked_at DESC LIMIT 5;
```

#### L7b — Deployment Governor
```bash
# Runs within full cycle — promotes strategies to paper/live
```

**Verify deployments:**
```sql
-- Deployment governance
SELECT strategy_id, mode, status, approved_by, activated_at
FROM deployment_governance ORDER BY proposed_at DESC LIMIT 10;
```

#### L7c — System Health
```sql
-- System health
SELECT checked_at, composite_score, system_mode, n_degraded
FROM system_health ORDER BY checked_at DESC LIMIT 5;
```

#### L7d — Pattern Memory
```sql
-- Pattern intelligence
SELECT pattern_type, archetype, composite_score_avg,
       confidence_score, recommendation, detected_at
FROM pattern_memory ORDER BY confidence_score DESC LIMIT 10;
```

---

### Scout Network

#### Internal Scouts (Regime, Liquidity, Correlation, Execution)
```bash
# Scouts run every 60-300 seconds within the full cycle
```

**Verify scout signals:**
```sql
-- Scout signals by source
SELECT source, COUNT(*) as cnt
FROM scout_signals
GROUP BY source ORDER BY cnt DESC;

-- Recent scout signals
SELECT source, symbol, signal_type, confidence_score, created_at
FROM scout_signals
ORDER BY created_at DESC LIMIT 20;

-- Unknown source signals (potential data quality issue)
SELECT COUNT(*) FROM scout_signals
WHERE source = 'unknown' OR source IS NULL;
```

#### External Scouts (Reddit, Discord, YouTube, News)
```sql
-- External scout memory
SELECT source, COUNT(*) as cnt
FROM external_scout_memory
GROUP BY source ORDER BY cnt DESC;

-- Recent external signals
SELECT source, sentiment, hypothesis_score, signal_direction, mentioned_tickers
FROM external_scout_memory
ORDER BY timestamp DESC LIMIT 10;
```

---

## 5. Running the Full Pipeline

### Option A: Full Autonomous Cycle (Recommended for Demo)
```bash
# Run for 30 minutes (all layers active)
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 30

# Run for 60 minutes
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 60

# Logs are saved to: logs/autonomous_cycle_YYYY-MM-DD_HHmmss.log
```

### Option B: Individual Layer Runs
```bash
# Seed data first
python atlas/scripts/seed_equity_data.py
python atlas/scripts/seed_historical_data.py

# Run generation + backtest + validation pipeline
python atlas/scripts/run_pipeline.py

# Run validator on pending strategies
# NOTE: This resets ALL failed_validation strategies to pending_validation
# and re-evaluates them. Use --help for options.
python atlas/scripts/run_validator.py

# Run mutator on repair candidates
python atlas/scripts/run_mutator.py --cycles 10

# Run overnight generation (longer cycles)
python atlas/scripts/run_overnight_generation.py --duration 30
```

### Option C: Soak Tests (Extended Runtime)
```bash
# 6-hour soak
python atlas/scripts/soak/soak_6h.py

# 12-hour soak
python atlas/scripts/soak/soak_12h.py

# 24-hour soak
python atlas/scripts/soak/soak_24h.py
```

---

## 6. Dashboard & API Endpoints

### Start the Dashboard Server
```bash
python -m uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000
```

### Open in Browser
```
http://localhost:8000/dashboard
```

### API Endpoints (JSON)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | System health check |
| `GET /dashboard` | Interactive HTML dashboard |
| **Strategy Pipeline** | |
| `GET /dashboard/api/overview` | System health + all counts |
| `GET /dashboard/api/pipeline` | Strategy lifecycle funnel |
| `GET /dashboard/api/traces?limit=20` | Recent lifecycle traces |
| **Scout Network** | |
| `GET /dashboard/api/scouts` | Internal + external scout signals |
| **Execution** | |
| `GET /dashboard/api/risk` | Risk state + copy trader status |
| `GET /dashboard/api/execution/logs?limit=50` | Recent execution log |
| `GET /dashboard/api/execution/realism` | Execution realism simulations |
| `GET /dashboard/api/execution/dead-letters` | Failed executions |
| **Portfolio** | |
| `GET /dashboard/api/portfolio` | Portfolio intelligence + allocation |
| `GET /dashboard/api/portfolio/optimizer` | Advanced optimization results |
| **Validation** | |
| `GET /dashboard/api/validation` | Walk-forward, Monte Carlo, overfitting |
| `GET /dashboard/api/features` | Feature importance rankings |
| **Governance** | |
| `GET /dashboard/api/governance/system-health` | System health assessment |
| `GET /dashboard/api/governance/event-store` | Event store timeline |
| `GET /dashboard/api/governance/audit` | Audit ledger |
| `GET /dashboard/api/governance/deployments` | Deployment records |
| `GET /dashboard/api/governance/replay-integrity` | Replay integrity score |
| **Risk (Phase 14)** | |
| `GET /dashboard/api/risk/systemic` | Systemic risk assessment |
| `GET /dashboard/api/risk/stress-test` | Stress test results |
| `GET /dashboard/api/risk/capital-preservation` | Capital preservation state |
| **Meta-Intelligence** | |
| `GET /dashboard/api/meta/prompts` | Prompt evolution templates |
| `GET /dashboard/api/meta/mutation-policy` | Mutation policy state |
| `GET /dashboard/api/meta/agent-governance` | Agent governance state |
| `GET /dashboard/api/meta-reasoning` | Meta-reasoning advisories |
| `GET /dashboard/api/hypotheses` | Hypothesis registry |
| `GET /dashboard/api/failure-analysis` | Failure diagnoses |
| `GET /dashboard/api/mutation-advisory` | Mutation policy trends |
| `GET /dashboard/api/scout-synthesis` | Scout consensus metrics |
| **Phase 32-33 Intelligence** | |
| `GET /dashboard/api/meta/mutation-families` | Mutation family rankings |
| `GET /dashboard/api/meta/dominant-organisms` | Dominant organisms |
| `GET /dashboard/api/meta/regime-specialization` | Regime specialization profiles |
| `GET /dashboard/api/meta/scout-rankings` | Scout predictive rankings |
| `GET /dashboard/api/meta/portfolio-evolution` | Portfolio evolution tracking |
| `GET /dashboard/api/meta/adaptive-intelligence` | Adaptive intelligence benchmarks |
| **Observability** | |
| `GET /dashboard/api/observability/metrics` | Monitoring fabric metrics |
| `GET /dashboard/api/observability/anomalies` | Anomaly observations |

### API with Authentication (Protected Endpoints)
```bash
# Generate an API key first (from DB), then:
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/strategies
```

---

## 7. DB Verification Queries

### Strategy Lifecycle Funnel
```sql
-- Full pipeline funnel (run this during demo to show flow)
SELECT status, COUNT(*) as cnt,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM strategies), 1) as pct
FROM strategies
GROUP BY status ORDER BY cnt DESC;
```

### Pipeline Velocity (Last Hour)
```sql
-- How many strategies were generated in the last hour
SELECT COUNT(*) as generated_1h
FROM strategies WHERE created_at > NOW() - INTERVAL '1 hour';

-- How many backtests completed in the last hour
SELECT COUNT(*) as backtests_1h
FROM backtest_results WHERE created_at > NOW() - INTERVAL '1 hour';

-- How many validations completed in the last hour
SELECT COUNT(*) as validated_1h
FROM strategies
WHERE status IN ('validated', 'elite', 'research_candidate')
  AND updated_at > NOW() - INTERVAL '1 hour';
```

### Top Performing Strategies
```sql
-- Best strategies by composite score
SELECT s.name, s.status, s.archetype, s.regime,
       b.short_window_score, b.win_rate, b.total_trades,
       b.sharpe_ratio, b.max_drawdown
FROM strategies s
JOIN backtest_results b ON b.strategy_id = s.id
WHERE s.status IN ('validated', 'elite', 'research_candidate')
ORDER BY b.short_window_score DESC
LIMIT 10;
```

### Cost Governance
```sql
-- Cost profile distribution
SELECT cost_profile_classification, COUNT(*) as cnt
FROM strategies
WHERE cost_profile_classification IS NOT NULL
GROUP BY cost_profile_classification ORDER BY cnt DESC;

-- Cost governance alerts
SELECT name, cost_governance_status, cost_efficiency_score,
       friction_burden_pct, expected_edge_per_trade_bps
FROM strategies
WHERE cost_governance_status = 'ALERT'
ORDER BY cost_efficiency_score ASC LIMIT 10;
```

### Evolutionary Metrics
```sql
-- Mutation lineage depth
SELECT s.name, COUNT(m.id) as mutation_depth
FROM strategies s
LEFT JOIN strategies m ON m.parent_id = s.id
WHERE s.parent_id IS NULL
GROUP BY s.name ORDER BY mutation_depth DESC LIMIT 10;

-- Archetype distribution
SELECT archetype, COUNT(*) as cnt,
       AVG(CASE WHEN status IN ('validated', 'elite') THEN 1.0 ELSE 0.0 END) as success_rate
FROM strategies
GROUP BY archetype ORDER BY cnt DESC;
```

### Scout Intelligence
```sql
-- Scout signal quality
SELECT source, signal_type,
       AVG(confidence_score) as avg_confidence,
       COUNT(*) as signal_count
FROM scout_signals
GROUP BY source, signal_type
ORDER BY avg_confidence DESC;

-- Regime detection
SELECT signal_data, confidence_score, created_at
FROM scout_signals
WHERE signal_type = 'regime'
ORDER BY created_at DESC LIMIT 5;
```

### Execution Quality
```sql
-- Execution success rate
SELECT state, COUNT(*) as cnt
FROM execution_log
GROUP BY state ORDER BY cnt DESC;

-- Slippage analysis
SELECT symbol, AVG(slippage_bps) as avg_slippage,
       COUNT(*) as trade_count
FROM execution_log
WHERE slippage_bps IS NOT NULL
GROUP BY symbol ORDER BY avg_slippage DESC;
```

### System Health
```sql
-- Overall system metrics
SELECT
  (SELECT COUNT(*) FROM strategies) as total_strategies,
  (SELECT COUNT(*) FROM backtest_results) as total_backtests,
  (SELECT COUNT(*) FROM paper_trades) as total_trades,
  (SELECT COALESCE(SUM(pnl), 0) FROM paper_trades) as total_pnl,
  (SELECT COUNT(*) FROM scout_signals) as total_scout_signals,
  (SELECT COUNT(*) FROM lifecycle_events) as total_lifecycle_events,
  (SELECT COUNT(DISTINCT trace_id) FROM lifecycle_events) as unique_traces,
  (SELECT COUNT(*) FROM pattern_memory) as total_patterns,
  (SELECT COUNT(*) FROM execution_dead_letter WHERE resolved = FALSE) as unresolved_dead_letters;
```

---

## 8. Troubleshooting

### Common Issues

**DB Connection Failed:**
```bash
# Check if PostgreSQL is running
# Windows:
netstat -an | findstr 5433
# Linux/Mac:
lsof -i :5433

# Restart if needed
# Windows:
net start postgresql
# Docker:
docker-compose up -d
```

**Redis Connection Failed:**
```bash
# Check Redis
redis-cli ping
# Expected: PONG

# Start Redis if needed
redis-server
```

**Agent Crashes in Full Cycle:**
```bash
# Check the log file for the specific agent error
tail -100 logs/autonomous_cycle_*.log | grep -i "error\|exception\|failed"

# The full_autonomous_cycle has auto-restart with exponential backoff
# Agents will be restarted automatically (up to 10 min cooldown)
```

**Kill Switch Activated:**
```bash
# Check kill switch status
curl http://localhost:8000/risk

# Deactivate via API (if auth enabled)
curl -X POST http://localhost:8000/kill_switch/deactivate
```

### Quick Diagnostic Commands
```bash
# Full system diagnostic
python -c "
import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
from sqlalchemy import text

async def diagnose():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    async with db.engine.connect() as conn:
        # Strategy counts
        r = await conn.execute(text('SELECT status, COUNT(*) FROM strategies GROUP BY status'))
        print('=== Strategy Status ===')
        for row in r:
            print(f'  {row[0]}: {row[1]}')

        # Backtest count
        r = await conn.execute(text('SELECT COUNT(*) FROM backtest_results'))
        print(f'Backtests: {r.scalar()}')

        # Trade count
        r = await conn.execute(text('SELECT COUNT(*) FROM paper_trades'))
        print(f'Paper Trades: {r.scalar()}')

        # Scout count
        r = await conn.execute(text('SELECT COUNT(*) FROM scout_signals'))
        print(f'Scout Signals: {r.scalar()}')
    await db.close()

asyncio.run(diagnose())
"
```

---

## Quick Demo Script (Copy-Paste Ready)

### Step 1: Pre-Demo Checklist
```bash
# Verify DB + Redis are running
python -c "from atlas.data.storage.timescale_client import TimescaleClient; from atlas.config.settings import settings; import asyncio; db=TimescaleClient(settings.database_url); asyncio.run(db.connect()); print('DB: OK'); asyncio.run(db.close())"
python -c "import asyncio; from redis.asyncio import Redis; r=Redis.from_url('redis://localhost:6379'); asyncio.run(r.ping()); print('Redis: OK')"

# Run migrations (required for Phase 31+ tables)
python atlas/scripts/phase31_db_migration.py

# Seed data if fresh DB
python atlas/scripts/seed_equity_data.py
```

### Step 2: Start Services
```powershell
# Terminal 1 — API Server + Dashboard
python -m uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Full Autonomous Cycle (30 min)
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 30
```

### Step 3: Open Dashboard
```
Browser: http://localhost:8000/dashboard
```

### Step 4: Monitor (in another terminal)
```powershell
# PowerShell — refresh every 10 seconds:
while ($true) { curl -s http://localhost:8000/dashboard/api/overview | python -m json.tool; Start-Sleep 10 }

# Or bash equivalent:
while true; do curl -s http://localhost:8000/dashboard/api/overview | python -m json.tool; sleep 10; done
```

### Step 5: Verify Key Metrics
```bash
# Pipeline funnel
curl -s http://localhost:8000/dashboard/api/pipeline | python -m json.tool

# Scout activity
curl -s http://localhost:8000/dashboard/api/scouts | python -m json.tool

# Execution status
curl -s http://localhost:8000/dashboard/api/risk | python -m json.tool

# System health
curl -s http://localhost:8000/dashboard/api/governance/system-health | python -m json.tool
```
