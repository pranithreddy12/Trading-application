# ATLAS Autonomous Trading System — Full Pipeline Demo Guide for Shakir

**Date:** May 29, 2026
**System:** ATLAS v1.0 — 7-Layer Autonomous Strategy Evolution Platform
**Demo Script:** `python atlas/scripts/full_autonomous_cycle.py`

---

## Table of Contents

1. [Demo Prerequisites & Setup](#1-demo-prerequisites--setup)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Step-by-Step Demo Commands](#3-step-by-step-demo-commands)
   - [Step 1: Environment & Infrastructure Check](#step-1-environment--infrastructure-check)
   - [Step 2: Database Schema Walkthrough](#step-2-database-schema-walkthrough)
   - [Step 3: Start the Autonomous Pipeline](#step-3-start-the-autonomous-pipeline)
   - [Step 4: Monitor Scout Network (L1)](#step-4-monitor-scout-network-l1)
   - [Step 5: Monitor Strategy Generation (L2)](#step-5-monitor-strategy-generation-l2)
   - [Step 6: Monitor Backtesting (L3)](#step-6-monitor-backtesting-l3)
   - [Step 7: Monitor Validation (L3)](#step-7-monitor-validation-l3)
   - [Step 8: Monitor Risk Layer (L4)](#step-8-monitor-risk-layer-l4)
   - [Step 9: Monitor Execution Layer (L5)](#step-9-monitor-execution-layer-l5)
   - [Step 10: Monitor Portfolio Layer (L6)](#step-10-monitor-portfolio-layer-l6)
   - [Step 11: Monitor Meta Layer (L7)](#step-11-monitor-meta-layer-l7)
   - [Step 12: Post-Run Analysis](#step-12-post-run-analysis)
4. [What Is Implemented — Full Feature Inventory](#4-what-is-implemented--full-feature-inventory)
5. [Run Log Analysis Summary](#5-run-log-analysis-summary)
6. [Database Tables Reference](#6-database-tables-reference)
7. [Key SQL Queries Cheat Sheet](#7-key-sql-queries-cheat-sheet)

---

## 1. Demo Prerequisites & Setup

### 1.1 Pre-Flight Check

Before starting the demo, ensure:

```bash
# 1. Docker containers running (PostgreSQL/TimescaleDB + Redis)
cd C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS
docker-compose ps

# Expected output:
# Name                    Command               State           Ports
# -------------------------------------------------------------------
# atlas-db     docker-entrypoint.sh postgres    Up      0.0.0.0:5432->5432/tcp
# atlas-redis  docker-entrypoint.sh redis-s...  Up      0.0.0.0:6379->6379/tcp

# 2. Verify database is accessible
docker exec atlas-db psql -U atlas -d atlas -c "SELECT 1 AS alive;"

# 3. Verify Redis is accessible
docker exec atlas-redis redis-cli ping
# Expected: PONG

# 4. Check Python environment
python --version    # Should be 3.11+
pip list 2>/dev/null | findstr "loguru redis asyncpg sqlalchemy"

# 5. Check environment variables (or .env file)
type .env 2>nul || echo "No .env found — using defaults"
```

### 1.2 Logging Setup

The pipeline logs to both stdout and a rotating log file:

```bash
# Log files are created under:
mkdir -p logs
logs/autonomous_cycle_2026-05-29_*.log
```

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ATLAS SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  L7 ── META INTELLIGENCE                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • ScoutSynthesisEngine     • DeploymentGovernor             │   │
│  │ • AntiPoisoningEngine      • SystemHealthEngine            │   │
│  │ • EconomicAttributionEngine • EconomicEfficiencyEngine      │   │
│  │ • FeatureEvolutionEngine   • AgentPerformanceGovernor       │   │
│  │ • EntropyGovernanceEngine  • MutationPolicyEngine           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L6 ── PORTFOLIO LAYER                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • PortfolioIntelligenceEngine                                 │   │
│  │ • CapitalAllocator   • EnsembleExecutionEngine                │   │
│  │ • AdvancedPortfolioOptimizer                                  │   │
│  │ • DriftDetectionEngine  • StrategyRetirementEngine            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L5 ── EXECUTION LAYER                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • ExecutionGateway  • ExecutionRealismEngine                 │   │
│  │ • OrderTracker      • PositionManager                        │   │
│  │ • DeadLetterManager • RecoveryManager                        │   │
│  │ • BrokerAdapter (SimulatorAdapter)                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L4 ── RISK LAYER                                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • RiskController      • CapitalPreservationEngine            │   │
│  │ • StressTestEngine    • SystemicRiskEngine                   │   │
│  │ • KillSwitch          • Entropy-Governed Leverage            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L3 ── VALIDATION LAYER                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • BacktestRunner      • ValidatorAgent                       │   │
│  │ • ShortWindowEvaluator • RegimeValidator                     │   │
│  │ • WalkForwardAnalyzer • MonteCarloSimulator                  │   │
│  │ • OverfittingDetector • CostStressTester                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L2 ── STRATEGY LAYER                                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • IdeatorAgentV2 (LLM-based strategy generation)             │   │
│  │ • CoderAgent (generates executable Python code)              │   │
│  │ • MutatorAgent (tournament-selected mutation)               │   │
│  │ • CombinerAgent (tournament-selected parent pairing)        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L1 ── SCOUT NETWORK                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • RegimeScout      • LiquidityScout                          │   │
│  │ • CorrelationScout • ExecutionScout                          │   │
│  │ • NewsIntelligenceEngine                                     │   │
│  │ • HypothesisValidationEngine                                 │   │
│  │ • SourceReliabilityEngine                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  L0 ── DATA INGESTION                                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • TimescaleDB (PostgreSQL + time-series)                     │   │
│  │ • Redis (pub/sub, state, locks, leases)                      │   │
│  │ • 20+ feature tables, 1.46M+ feature records                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Demo Commands

### STEP 1: Environment & Infrastructure Check

**Purpose:** Verify all system components are operational before starting the pipeline.

```bash
# 1.1 Check Docker containers
echo "=== Checking Docker Containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 1.2 Verify database tables exist
echo "=== Database Tables ==="
docker exec atlas-db psql -U atlas -d atlas -c "\dt"

# 1.3 Check table row counts (live stats)
echo "=== Table Row Counts ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    schemaname || '.' || tablename AS table_name,
    n_live_tup AS estimated_rows
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
"

# 1.4 Check Redis connectivity
echo "=== Redis Info ==="
docker exec atlas-redis redis-cli INFO server | findstr "redis_version uptime_in_seconds"
```

**Expected Results:**
- Docker: Both `atlas-db` and `atlas-redis` should be "Up"
- Database: 20+ tables visible
- Redis: Version shown, uptime > 0

---

### STEP 2: Database Schema Walkthrough

**Purpose:** Show Shakir the complete database schema — every table and its purpose.

```sql
-- 2.1 CORE TABLES
-- ================

-- Market Data (Time-series, TimescaleDB hypertables)
\d+ market_data_l1
\d+ market_data_l2
\d+ order_flow
\d+ features

-- Strategy Lifecycle
\d+ strategies
\d+ backtest_results
\d+ backtest_trades

-- Execution
\d+ paper_trades
\d+ execution_log
\d+ execution_dead_letter

-- Portfolio & Risk
\d+ capital_allocation
\d+ risk_state
\d+ positions

-- Audit & Governance
\d+ event_store
\d+ audit_ledger
\d+ lifecycle_events
\d+ system_logs

-- Scout Network
\d+ market_regime_memory
\d+ liquidity_intelligence
\d+ correlation_memory
\d+ execution_intelligence
\d+ scout_signals
\d+ external_scout_memory
\d+ scout_quarantine

-- Meta Intelligence
\d+ deployment_governance
\d+ feature_importance
\d+ drift_detection
\d+ pattern_memory
\d+ mutation_memory
\d+ combination_memory
\d+ strategy_lineage
```

**Key Schema Notes for Shakir:**
- `features` is the largest table (~1.46M rows) — stores normalized feature values (RSI, VWAP, Bollinger, etc.)
- `strategies` (~2,538 rows) — the master strategy registry with lifecycle status tracking
- `backtest_results` (~2,518 rows) — backtest metrics (Sharpe, drawdown, win rate, composite score)
- `event_store` (~4,457 rows) — event sourcing with hash chain for audit integrity
- `audit_ledger` (~5,301 rows) — operator and agent action tracking

---

### STEP 3: Start the Autonomous Pipeline

**Purpose:** Launch all agents simultaneously.

```bash
# 3.1 Start the full autonomous pipeline (default 60 min runtime)
cd C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 60

# Alternative: Shorter demo run
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 30

# Alternative: Longer run with specific log file
python atlas/scripts/full_autonomous_cycle.py --duration-minutes 120 --log-file logs/shakir_demo.log
```

**What happens when you run this:**
1. **Infrastructure boots:** TimescaleDB connects, Redis connects
2. **Paper trades sync:** Existing execution history synced to paper_trades table
3. **Agent factory activates:** 40+ agents created across all 7 layers
4. **Soak monitor starts:** Captures metrics every 300 seconds
5. **All agents start in parallel:** Each agent gets its own asyncio task
6. **Supervisor loop runs:** Monitors agent health, auto-restarts failed agents with exponential backoff
7. **Graceful shutdown:** All agents stopped, connections closed

**Expected Output:**
```
2026-05-29 10:00:00.000 | INFO     | full_autonomous_cycle:main | Logging to file: ...
2026-05-29 10:00:00.500 | INFO     | full_autonomous_cycle:main | SoakMonitor started
2026-05-29 10:00:01.000 | INFO     | full_autonomous_cycle:main | Starting institutional cycle
2026-05-29 10:00:01.500 | INFO     | RegimeScout:start | Agent started
2026-05-29 10:00:01.600 | INFO     | LiquidityScout:start | Agent started
... (35+ agents starting)
```

---

### STEP 4: Monitor Scout Network (L1)

**Purpose:** Scouts are the "sensors" of the system, continuously analyzing market conditions.

**Run these queries DURING the pipeline execution (in a second terminal):**

```bash
# 4.1 Check Regime Scout — market regime classification
echo "=== REGIME SCOUT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT symbol, volatility_regime, trend_regime, liquidity_regime,
       correlation_regime, confidence_score, timestamp
FROM market_regime_memory
ORDER BY timestamp DESC
LIMIT 10;
"

# Expected: Shows current regime for each symbol (e.g., trending, ranging, high_vol)
```

```bash
# 4.2 Check Liquidity Scout
echo "=== LIQUIDITY SCOUT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT symbol, liquidity_score, slippage_risk, liquidity_regime, timestamp
FROM liquidity_intelligence
ORDER BY timestamp DESC
LIMIT 10;
"

# Expected: Shows liquidity health (healthy/thin/dangerous) with scores
```

```bash
# 4.3 Check Correlation Scout
echo "=== CORRELATION SCOUT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT cluster_name, avg_pairwise_corr, risk_state, correlation_spike_detected, timestamp
FROM correlation_memory
ORDER BY timestamp DESC
LIMIT 5;
"

# Expected: Correlation clusters with risk state (normal/panic_correlation)
```

```bash
# 4.4 Check Execution Scout
echo "=== EXECUTION SCOUT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT symbol, avg_slippage_bps, fill_quality_score, execution_regime, timestamp
FROM execution_intelligence
ORDER BY timestamp DESC
LIMIT 5;
"

# Expected: Shows execution quality (healthy/degraded/unstable)
```

```bash
# 4.5 Check Scout Signals Total
echo "=== SCOUT SIGNALS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT COUNT(*) AS total_signals,
       COUNT(DISTINCT source) AS unique_sources
FROM scout_signals;
"
```

**What Shakir should observe:**
- Scouts generate signals continuously (regime, liquidity, correlation, execution)
- Each scout has its own table with time-stamped observations
- Confidence scores and risk states are tracked
- Scout data feeds into higher layers (L7 synthesis, L2 ideation, L5 execution)

---

### STEP 5: Monitor Strategy Generation (L2)

**Purpose:** Strategies are generated by the IdeatorAgent (via LLM), coded by the CoderAgent, and optionally mutated/combined.

```bash
# 5.1 Check Strategy Counts by Status (live)
echo "=== STRATEGY ECOSYSTEM ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT status, COUNT(*) AS count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM strategies
GROUP BY status
ORDER BY count DESC;
"

# Expected: failed_validation (~90%), validated (~6%), research_candidate (~3%)
```

```bash
# 5.2 Check Recently Generated Strategies
echo "=== RECENT STRATEGIES ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT id, name, status, created_at,
       LEFT(parameters::text, 80) AS params_preview
FROM strategies
ORDER BY created_at DESC
LIMIT 10;
"

# Shows: Strategy ID, unique name (e.g., momentum_nvda_ema_spread_1234), current status
```

```bash
# 5.3 Check Strategy Archetype Distribution
echo "=== ARCHETYPE DISTRIBUTION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    (parameters->>'archetype') AS archetype,
    COUNT(*) AS count
FROM strategies
WHERE parameters->>'archetype' IS NOT NULL
GROUP BY archetype
ORDER BY count DESC;
"

# Expected: momentum, mean_reversion, breakout, volatility_regime, trend_following
```

```bash
# 5.4 Check Mutator Activity
echo "=== MUTATOR OUTPUT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT COUNT(*) AS total_mutations
FROM combination_memory;
"

-- Check strategies generated by mutation (named with _mut_ or _v2, _v3, etc.)
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT name, status, parameters->>'archetype' AS archetype
FROM strategies
WHERE name LIKE '%mut%' OR name LIKE '%v2%' OR name LIKE '%v3%'
ORDER BY created_at DESC
LIMIT 10;
"
```

**What Shakir should observe:**
- Thousands of strategies in the system with different lifecycle statuses
- Strategies have unique names following convention: `{archetype}_{ticker}_{feature}_{timestamp}`
- Archetype diversity across multiple classes (momentum, mean_reversion, etc.)
- Mutation creates variant strategies (v2, v3, etc.)

---

### STEP 6: Monitor Backtesting (L3)

**Purpose:** Each strategy is backtested against historical 1-minute data with dynamic slippage and commission modeling.

```bash
# 6.1 Backtest Metrics Overview
echo "=== BACKTEST METRICS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    COUNT(*) AS total_backtests,
    ROUND(AVG(short_window_score)::numeric, 2) AS avg_score,
    ROUND(AVG(sharpe)::numeric, 4) AS avg_sharpe,
    ROUND(AVG(win_rate)::numeric, 4) AS avg_win_rate,
    ROUND(AVG(max_drawdown)::numeric, 2) AS avg_max_dd,
    ROUND(AVG(total_trades)::numeric, 1) AS avg_trades
FROM backtest_results;
"
```

```bash
# 6.2 Top Performing Strategies
echo "=== TOP 10 STRATEGIES ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT s.name, s.status,
       b.short_window_score, b.sharpe, b.win_rate, b.total_trades,
       b.composite_fitness
FROM strategies s
JOIN backtest_results b ON s.id = b.strategy_id
WHERE b.short_window_score IS NOT NULL
ORDER BY b.composite_fitness DESC
LIMIT 10;
"

# Shows: Top strategies ranked by composite fitness score
```

```bash
# 6.3 Sharpe Distribution
echo "=== SHARPE DISTRIBUTION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    CASE
        WHEN sharpe >= 2.0 THEN '>= 2.0 (Excellent)'
        WHEN sharpe >= 1.0 THEN '1.0 - 2.0 (Good)'
        WHEN sharpe >= 0.5 THEN '0.5 - 1.0 (Fair)'
        WHEN sharpe >= 0.0 THEN '0.0 - 0.5 (Poor)'
        ELSE 'Negative'
    END AS sharpe_bucket,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM backtest_results
GROUP BY sharpe_bucket
ORDER BY sharpe_bucket;
"
```

**What Shakir should observe:**
- 2,500+ backtest results with full metrics
- Average Sharpe ~0.17 (typical for 1-min strategies), with outliers up to 140
- Top strategies have composite fitness scores of 42+
- Sharpe distribution shows the long tail of strategy performance

---

### STEP 7: Monitor Validation (L3)

**Purpose:** Strategies go through a multi-stage validation pipeline.

```bash
# 7.1 Validation Pipeline Status
echo "=== VALIDATION STATUS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    COUNT(*) FILTER (WHERE status = 'validated') AS validated,
    COUNT(*) FILTER (WHERE status = 'failed_validation') AS failed,
    COUNT(*) FILTER (WHERE status = 'research_candidate') AS research,
    COUNT(*) FILTER (WHERE status = 'pending_validation') AS pending,
    COUNT(*) FILTER (WHERE status = 'elite') AS elite,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status IN ('validated','elite','research_candidate')) / GREATEST(COUNT(*), 1), 1) AS pass_rate
FROM strategies;
"
```

```bash
# 7.2 Validation Notes for Top Strategies
echo "=== VALIDATION METRICS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT name, status,
       validation_notes::json->>'composite_score' AS comp_score,
       validation_notes::json->>'tier' AS tier,
       validation_notes::json->>'cost_governance_status' AS cost_gov
FROM strategies
WHERE validation_notes IS NOT NULL AND status IN ('validated', 'research_candidate')
ORDER BY created_at DESC
LIMIT 10;
"
```

```bash
# 7.3 Walk-Forward & Overfitting Analysis
echo "=== WALK-FORWARD / OVERFIT ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    COUNT(*) AS total_analyzed,
    ROUND(AVG(walk_forward_score)::numeric, 2) AS avg_wf_score,
    ROUND(AVG(overfit_probability)::numeric, 4) AS avg_overfit_prob
FROM walk_forward_analysis;
" 2>nul || echo "Table may not exist yet — run pipeline first"

docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    COUNT(*) AS total_tested,
    ROUND(AVG(survival_rate)::numeric, 4) AS avg_survival_rate
FROM monte_carlo_analysis;
" 2>nul || echo "Table may not exist yet"
```

**What Shakir should observe:**
- ~9% pass rate (151 validated + 75 research candidates out of 2,538)
- Validation stores complete metrics as JSONB in `validation_notes`
- Multiple validation stages: structural sanity → composite scoring → tier assignment → cost governance
- Walk-forward, Monte Carlo, and overfitting analyses available

---

### STEP 8: Monitor Risk Layer (L4)

**Purpose:** The risk layer protects capital with multi-layered governance.

```bash
# 8.1 Risk State
echo "=== RISK STATE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT scope, halted, max_drawdown, daily_loss, weekly_loss,
       entropy_leverage_cap, created_at
FROM risk_state
ORDER BY created_at DESC
LIMIT 5;
"
```

```bash
# 8.2 Capital Preservation State
echo "=== CAPITAL PRESERVATION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_id, drawdown_pct, exposure_reduction_pct,
       capital_frozen, trigger_reason, updated_at
FROM capital_preservation_state
ORDER BY updated_at DESC
LIMIT 10;
" 2>nul || echo "Table may not have data yet"

# 8.3 Kill Switch Status
echo "=== KILL SWITCH CHECK ==="
docker exec atlas-redis redis-cli HGETALL "kill_switch:state"
# Expected: (empty list) if not active, or shows reason if triggered
```

**Key Risk Limits:**
| Limit | Threshold | Action |
|-------|-----------|--------|
| Daily Loss | -2% | Kill switch triggered |
| Weekly Loss | -4% | Kill switch triggered |
| Max Drawdown | -15% | Capital freeze |
| Single Position | 10% (5% in high disagreement) | Trade rejection |
| Open Positions | 10 max | Trade rejection |
| Cash Reserve | 20% minimum | Trade rejection |
| High Entropy (>0.7) | 50% leverage cap | Position sizing reduced |

---

### STEP 9: Monitor Execution Layer (L5)

**Purpose:** Paper trading and execution simulation.

```bash
# 9.1 Paper Trades
echo "=== PAPER TRADES ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT side, COUNT(*) AS count,
       ROUND(AVG(price)::numeric, 2) AS avg_price,
       ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) AS total_pnl
FROM paper_trades
GROUP BY side;
"

# 9.2 Execution Log
echo "=== EXECUTION LOG ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_id, symbol, side, quantity, price, status, created_at
FROM execution_log
ORDER BY created_at DESC
LIMIT 10;
"

# 9.3 Dead Letter Queue
echo "=== DEAD LETTER QUEUE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_id, symbol, side, failure_reason, severity, created_at
FROM execution_dead_letter
ORDER BY created_at DESC
LIMIT 10;
"

# 9.4 Deployment Governance
echo "=== DEPLOYMENT GOVERNANCE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_id, mode, status, proposed_by, proposed_at
FROM deployment_governance
ORDER BY proposed_at DESC
LIMIT 10;
"
```

---

### STEP 10: Monitor Portfolio Layer (L6)

**Purpose:** Portfolio optimization and allocation.

```bash
# 10.1 Capital Allocation
echo "=== CAPITAL ALLOCATION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT id, computed_at, n_strategies, total_exposure,
       diversification_score, concentration_risk
FROM capital_allocation
ORDER BY computed_at DESC
LIMIT 5;
"

# 10.2 Current Allocations Detail
echo "=== STRATEGY ALLOCATIONS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_name, weight, score, sharpe, allocated_at
FROM strategy_allocations
ORDER BY weight DESC
LIMIT 10;
" 2>nul || echo "Check capital_allocation table for allocation details"

# 10.3 Drift Detection
echo "=== DRIFT DETECTION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT strategy_id, drift_type, drift_score, severity, detected_at
FROM drift_detection
ORDER BY detected_at DESC
LIMIT 10;
"

# 10.4 Portfolio Evolution
echo "=== PORTFOLIO EVOLUTION ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT diversification_score, correlation_collapse_risk,
       contagion_exposure, concentration_risk,
       portfolio_survivability, active_strategies
FROM portfolio_evolution_log
ORDER BY computed_at DESC
LIMIT 5;
" 2>nul || echo "Table may not exist yet"
```

---

### STEP 11: Monitor Meta Layer (L7)

**Purpose:** The "brain" of the system — governs and improves all other layers.

```bash
# 11.1 Scout Synthesis (cross-scout consensus)
echo "=== SCOUT SYNTHESIS ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT id, confidence, contextual_summary,
       scout_agreement_score, market_state_interpretation,
       created_at
FROM scout_synthesis_log
ORDER BY created_at DESC
LIMIT 5;
"

# 11.2 System Health
echo "=== SYSTEM HEALTH ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT agent_id, health_score, component_status, degraded_components, checked_at
FROM system_health_log
ORDER BY checked_at DESC
LIMIT 5;
" 2>nul || echo "Table may not have data yet"

# 11.3 Agent Performance
echo "=== AGENT PERFORMANCE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT agent_name, avg_response_time, success_rate, total_operations, last_updated
FROM agent_performance_metrics
ORDER BY last_updated DESC
LIMIT 10;
" 2>nul || echo "Table may not have data yet"

# 11.4 Feature Importance Tracking
echo "=== FEATURE IMPORTANCE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT feature_name, importance_score, survival_rate, decay_rate, tracked_at
FROM feature_importance
ORDER BY importance_score DESC
LIMILT 10;
"

# 11.5 Event Store (Audit Trail)
echo "=== EVENT STORE ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT aggregate_type, event_type,
       COUNT(*) AS count,
       COUNT(hash_self) AS hashed
FROM event_store
GROUP BY aggregate_type, event_type
ORDER BY count DESC
LIMILT 15;
"

# 11.6 Audit Ledger
echo "=== AUDIT LEDGER ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT actor, action, target_type,
       COUNT(*) AS count,
       COUNT(hash_self) AS hashed
FROM audit_ledger
GROUP BY actor, action, target_type
ORDER BY count DESC
LIMILT 15;
"
```

---

### STEP 12: Post-Run Analysis

**Purpose:** After the pipeline completes, run comprehensive analysis.

```bash
# 12.1 Run the post-soak analysis script
cd C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS
python atlas/scripts/post_soak_analysis.py

# This generates a complete JSON report saved to post_soak_analysis_results.json
```

```bash
# 12.2 Quick Database Health Check
echo "=== DATABASE HEALTH ==="
docker exec atlas-db psql -U atlas -d atlas -c "
SELECT
    'strategies' AS table_name, COUNT(*) FROM strategies
    UNION ALL
    SELECT 'backtest_results', COUNT(*) FROM backtest_results
    UNION ALL
    SELECT 'backtest_trades', COUNT(*) FROM backtest_trades
    UNION ALL
    SELECT 'features', COUNT(*) FROM features
    UNION ALL
    SELECT 'event_store', COUNT(*) FROM event_store
    UNION ALL
    SELECT 'audit_ledger', COUNT(*) FROM audit_ledger
    UNION ALL
    SELECT 'lifecycle_events', COUNT(*) FROM lifecycle_events
    UNION ALL
    SELECT 'paper_trades', COUNT(*) FROM paper_trades
    UNION ALL
    SELECT 'system_logs', COUNT(*) FROM system_logs
    UNION ALL
    SELECT 'execution_log', COUNT(*) FROM execution_log
ORDER BY table_name;
"
```

```bash
# 12.3 Overall System Summary
echo "=== SYSTEM SUMMARY ==="
docker exec atlas-db psql -U atlas -d atlas -c "
WITH strategy_stats AS (
    SELECT
        COUNT(*) AS total_strategies,
        COUNT(*) FILTER (WHERE status = 'validated') AS validated,
        COUNT(*) FILTER (WHERE status = 'failed_validation') AS failed,
        COUNT(*) FILTER (WHERE status = 'research_candidate') AS research
    FROM strategies
),
backtest_stats AS (
    SELECT
        ROUND(AVG(short_window_score)::numeric, 2) AS avg_score,
        ROUND(AVG(sharpe)::numeric, 4) AS avg_sharpe,
        ROUND(AVG(win_rate)::numeric, 4) AS avg_win_rate
    FROM backtest_results
)
SELECT
    total_strategies,
    validated,
    failed,
    research,
    ROUND(100.0 * validated / NULLIF(total_strategies, 0), 1) AS pass_rate_pct,
    avg_score,
    avg_sharpe,
    avg_win_rate
FROM strategy_stats, backtest_stats;
"
```

---

## 4. What Is Implemented — Full Feature Inventory

### ✅ L0 — Data Ingestion & Infrastructure

| Feature | Status | Details |
|---------|--------|---------|
| TimescaleDB | ✅ Operational | Hypertables for market_data_l1, market_data_l2, order_flow, features |
| Redis Pub/Sub | ✅ Operational | Agent communication, state management, distributed locks |
| Features Table | ✅ 1.46M rows | RSI, VWAP, Bollinger Bands, EMA, ATR, volatility, 20+ features |
| Event Store | ✅ 4,457 entries | Full event sourcing with hash chain integrity |
| Audit Ledger | ✅ 5,301 entries | Operator and agent action tracking |
| System Logs | ✅ 3,238 entries | Structured logging per agent |

### ✅ L1 — Scout Network

| Agent | Status | Output |
|-------|--------|--------|
| RegimeScout | ✅ Active | market_regime_memory (472 entries/run) |
| LiquidityScout | ✅ Active | liquidity_intelligence (240 entries/run) |
| CorrelationScout | ✅ Active | correlation_memory (12 entries/run) |
| ExecutionScout | ✅ Active | execution_intelligence |
| NewsIntelligenceEngine | ✅ Active | external_scout_memory |
| HypothesisValidationEngine | ✅ Active | external_scout_memory with hypothesis scoring |
| SourceReliabilityEngine | ✅ Active | Dynamic trust scores per source |

**Scout Synthesis (L7):** ScoutSynthesisEngine aggregates all scout signals into confidence-weighted narratives with agreement/disagreement metrics.

### ✅ L2 — Strategy Layer

| Agent | Status | Details |
|-------|--------|---------|
| IdeatorAgentV2 | ✅ Active | LLM-based generation with 5 archetypes, regime-aware, diversity governance |
| CoderAgent | ✅ Active | Generates executable Python code with compile validation |
| MutatorAgent | ✅ Active | Tournament selection (size=7) from 30 candidates → 5 winners → mutants |
| CombinerAgent | ✅ Active | Tournament selection (size=5) for untried parent pairs |
| Strategy Normalizer | ✅ Active | Normalizes entry/exit conditions, valid regimes, hold times |

**Generation Features:**
- Archetype distribution: momentum, mean_reversion, breakout, volatility_regime, trend_following
- Asset classes: equity and crypto
- Timeframes: 1-minute (primary)
- Ecological pressure modulation
- Diversity governance (adaptive similarity thresholds)
- Feature family distribution tracking
- Threshold memory from successful strategies

### ✅ L3 — Validation Layer

| Component | Status | Details |
|-----------|--------|---------|
| BacktestRunner | ✅ Active | Dynamic slippage (1.5-18 bps), commission modeling |
| ShortWindowEvaluator | ✅ Active | 60/20/20 train/holdout/test split |
| ValidatorAgent | ✅ Active | Multi-stage: structural → composite scoring → tier assignment |
| WalkForwardAnalyzer | ✅ Active | Train vs holdout Sharpe consistency |
| MonteCarloSimulator | ✅ Active | Statistical robustness testing |
| OverfittingDetector | ✅ Active | Overfit probability estimation |
| CostStressTester | ✅ Active | Edge-per-trade minimums |
| RegimeValidator | ✅ Active | Multi-regime survival validation |

**Tier Assignment:**
| Score Range | Tier (Dev) | Tier (Production) |
|-------------|-----------|-------------------|
| 90-100 | N/A | Elite |
| 70-89 | N/A | Validated |
| 60-69 | Elite | Research Candidate |
| 35-59 | Validated | Repair Candidate |
| 25-34 | Research Candidate | Failed |
| 15-24 | Repair Candidate | Failed |
| < 15 | Failed | Failed |

**Structural Validation Gates:**
- Minimum entry count: 2 (dev: 1)
- Minimum total trades: 2 (dev: 1)
- Max entry saturation: 60%
- Max exit saturation: 95%

### ✅ L4 — Risk Layer

| Component | Status | Details |
|-----------|--------|---------|
| RiskController | ✅ Active | Position sizing, max positions, cash reserve |
| CapitalPreservationEngine | ✅ Active | Drawdown-based exposure reduction |
| StressTestEngine | ✅ Active | Scenario-based portfolio stress testing |
| SystemicRiskEngine | ✅ Active | Cross-strategy correlation + contagion analysis |
| KillSwitch | ✅ Active | Emergency stop via Redis |
| Entropy-Governed Leverage | ✅ Active | High entropy → 50% leverage cap |

### ✅ L5 — Execution Layer

| Component | Status | Details |
|-----------|--------|---------|
| ExecutionGateway | ✅ Active | Idempotent order execution with retry |
| OrderTracker | ✅ Active | Full order state machine (10+ states) |
| PositionManager | ✅ Active | Open/close positions |
| DeadLetterManager | ✅ Active | Failed order routing |
| RecoveryManager | ✅ Active | Startup reconciliation |
| ExecutionRealismEngine | ✅ Active | Fill probability, slippage, latency simulation |
| BrokerAdapter (Simulator) | ✅ Active | Paper trading simulation |

**Order States:** SIGNAL_RECEIVED → RISK_APPROVED → BROKER_ACK → FILLED / PARTIALLY_FILLED / FILL_TIMEOUT / CANCELLED / RISK_REJECTED / KILL_SWITCH_BLOCKED / DEAD_LETTER

### ✅ L6 — Portfolio Layer

| Component | Status | Details |
|-----------|--------|---------|
| PortfolioIntelligenceEngine | ✅ Active | Correlation matrices, exposure clustering |
| CapitalAllocator | ✅ Active | Mean-variance optimization |
| EnsembleExecutionEngine | ✅ Active | Signal aggregation |
| AdvancedPortfolioOptimizer | ✅ Active | Risk-parity optimization |
| DriftDetectionEngine | ✅ Active | Feature/strategy/regime drift |
| StrategyRetirementEngine | ✅ Active | Underperformer detection |

### ✅ L7 — Meta Layer

| Component | Status | Details |
|-----------|--------|---------|
| ScoutSynthesisEngine | ✅ Active | Confidence-weighted consensus |
| DeploymentGovernor | ✅ Active | Tournament selection for paper promotion |
| SystemHealthEngine | ✅ Active | Composite health scoring |
| AntiPoisoningEngine | ✅ Active | Adversarial signal filtering |
| EconomicAttributionEngine | ✅ Active | PnL attribution |
| EconomicEfficiencyEngine | ✅ Active | Capital efficiency scoring |
| EntropyGovernanceEngine | ✅ Active | Regulation via entropy |
| MutationPolicyEngine | ✅ Active | Exploration vs exploitation |
| FeatureEvolutionEngine | ✅ Active | Feature importance tracking |
| AgentPerformanceGovernor | ✅ Active | Agent-level performance monitoring |

### ✅ Tournament Selection System (Phase 37B)

| Usage | Function | Tournament Size |
|-------|----------|-----------------|
| MutatorAgent | `tournament_select()` | 7 |
| CombinerAgent | `tournament_select_unique()` | 5 |
| DeploymentGovernor | `tournament_select_unique()` | 5 |

**Key Properties:**
- Top candidate wins only ~24% (not 100%) — confirms exploration
- 20+ distinct candidates selected from pool of 30
- Smaller tournament_size = more diversity
- 25 unit tests all passing

---

## 5. Run Log Analysis Summary

### 5.1 Previous Run Results (Phase 25 Soak — 60-min run)

**Scout Network Performance:**
| Time | Scout Signals | Regime Scout | Liquidity Scout | Correlation Scout |
|------|--------------|--------------|-----------------|-------------------|
| t=5min | 65 | 40 | 24 | 1 |
| t=10min | 122 | 80 | 40 | 2 |
| t=30min | 366 | 240 | 120 | 6 |
| t=60min | 724 | 472 | 240 | 12 |

**Scouts are actively generating signals every ~45 seconds.**

**Database State (Post-Soak):**
| Table | Row Count |
|-------|-----------|
| strategies | 1,806 |
| backtest_results | 1,307 |
| backtest_trades | 584,606 |
| lifecycle_events | 5,641 |
| event_store | 4,457 |
| audit_ledger | 5,301 |
| pattern_memory | 2,467 |
| system_logs | 3,238 |
| **Total** | **608,925** |

**Backtest Performance:**
| Metric | Value |
|--------|-------|
| Total Backtests | 1,307 |
| Avg Short Window Score | 35.08 |
| Avg Sharpe | 0.00 (fixed in Phase 38 with per-trade Sharpe) |
| Avg Win Rate | 19.22% |

**Top Strategy Scores:** 42.6 (nvda_rsi_bb_vwap_breakout_v3), 42.3 (breakout strategies)

**Agent Health:** 5,641 lifecycle events, 13 unique agents, 0 crashes.

### 5.2 Phase 38 Pipeline Validation (Most Recent)

| Layer | Result |
|-------|--------|
| L0 Ingestion | ✅ 1,458,631 feature records |
| L1 Strategy Gen | ✅ 2,538 total strategies |
| L2 Backtest | ✅ 2,518 results (avg Sharpe 0.17) |
| L3 Validation | ✅ 2,292 processed — 151 validated + 75 research = 9% pass |
| L4 Risk | ✅ All 3 risk engines operational |
| L5 Mutation | ✅ 10 new mutants via tournament selection |
| L6 Portfolio | ✅ 151 strategies eligible |
| L7 Deployment | ✅ 7 strategies promoted to paper via tournament |

---

## 6. Database Tables Reference

| Schema | Table | Purpose | Est. Rows |
|--------|-------|---------|-----------|
| `public` | `market_data_l1` | Level 1 tick data (bid/ask) | Timescale hypertable |
| `public` | `market_data_l2` | Level 2 order book data | Timescale hypertable |
| `public` | `order_flow` | Order flow analysis | Timescale hypertable |
| `public` | `features` | Computed technical features (RSI, VWAP, etc.) | ~1.46M |
| `public` | `strategies` | Strategy registry (master table) | ~2,538 |
| `public` | `backtest_results` | Backtest metrics per strategy | ~2,518 |
| `public` | `backtest_trades` | Individual backtest trade records | ~584K |
| `public` | `paper_trades` | Simulated paper trades | Variable |
| `public` | `execution_log` | Live execution records | ~107 |
| `public` | `execution_dead_letter` | Failed order records | ~0 |
| `public` | `risk_state` | Risk system state | Variable |
| `public` | `positions` | Open position tracking | ~0 |
| `public` | `event_store` | Event sourcing with hash chain | ~4,457 |
| `public` | `audit_ledger` | Operator/agent action audit | ~5,301 |
| `public` | `lifecycle_events` | Agent lifecycle tracking | ~5,641 |
| `public` | `system_logs` | Structured system logging | ~3,238 |
| `public` | `capital_allocation` | Capital allocation snapshots | ~9 |
| `public` | `market_regime_memory` | Regime scout output | Variable |
| `public` | `liquidity_intelligence` | Liquidity scout output | Variable |
| `public` | `correlation_memory` | Correlation scout output | Variable |
| `public` | `execution_intelligence` | Execution scout output | Variable |
| `public` | `scout_signals` | Aggregated scout signals | ~0 |
| `public` | `external_scout_memory` | External scout (news, social) | ~0 |
| `public` | `scout_quarantine` | Quarantined/poisoned signals | ~0 |
| `public` | `pattern_memory` | Pattern recognition results | ~2,467 |
| `public` | `feature_importance` | Feature importance tracking | ~22 |
| `public` | `drift_detection` | Drift monitoring records | ~10 |
| `public` | `deployment_governance` | Deployment lifecycle | Variable |
| `public` | `mutation_memory` | Mutation history | Variable |
| `public` | `combination_memory` | Combination history | Variable |
| `public` | `copy_execution_log` | Copy trading execution | ~7 |
| `public` | `failed_inserts` | Dead-letter for DB errors | ~53 |
| `public` | `agent_registry` | Agent registration | ~0 |

---

## 7. Key SQL Queries Cheat Sheet

### Strategy Analytics
```sql
-- Best performing strategies
SELECT s.name, s.status, b.short_window_score, b.sharpe, b.win_rate, b.total_trades
FROM strategies s JOIN backtest_results b ON s.id = b.strategy_id
ORDER BY b.composite_fitness DESC LIMIT 20;

-- Strategies by status with percentages
SELECT status, COUNT(*) AS count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM strategies GROUP BY status ORDER BY count DESC;

-- Recently generated strategies
SELECT id, name, status, parameters->>'archetype' AS archetype, created_at
FROM strategies ORDER BY created_at DESC LIMIT 20;
```

### Backtest Analytics
```sql
-- Backtest metrics summary
SELECT COUNT(*) AS total,
       ROUND(AVG(short_window_score)::numeric, 2) AS avg_score,
       ROUND(AVG(sharpe)::numeric, 4) AS avg_sharpe,
       ROUND(AVG(win_rate)::numeric, 4) AS avg_win_rate,
       ROUND(AVG(total_trades)::numeric, 1) AS avg_trades
FROM backtest_results;

-- Sharpe bucket distribution
SELECT CASE WHEN sharpe >= 2.0 THEN 'Excellent (≥2.0)'
            WHEN sharpe >= 1.0 THEN 'Good (1.0-2.0)'
            WHEN sharpe >= 0.5 THEN 'Fair (0.5-1.0)'
            WHEN sharpe >= 0.0 THEN 'Poor (0.0-0.5)'
            ELSE 'Negative' END AS bucket,
       COUNT(*) AS count
FROM backtest_results GROUP BY bucket ORDER BY bucket;
```

### Scout Network Analytics
```sql
-- Scout activity summary
SELECT source, COUNT(*) AS signals,
       MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen
FROM scout_signals GROUP BY source ORDER BY signals DESC;

-- Current market regime
SELECT symbol, volatility_regime, trend_regime, confidence_score
FROM market_regime_memory ORDER BY timestamp DESC LIMIT 5;
```

### Audit & Governance
```sql
-- Event store activity by aggregate type
SELECT aggregate_type, event_type, COUNT(*) AS count
FROM event_store GROUP BY aggregate_type, event_type ORDER BY count DESC;

-- Audit ledger by actor
SELECT actor, action, target_type, COUNT(*) AS count
FROM audit_ledger GROUP BY actor, action, target_type ORDER BY count DESC;

-- Lifecycle events (agent health)
SELECT actor, stage, COUNT(*) AS count
FROM lifecycle_events GROUP BY actor, stage ORDER BY actor;
```

### Deployment & Execution
```sql
-- Current deployed strategies
SELECT s.name, d.mode, d.status, d.proposed_by, d.proposed_at
FROM deployment_governance d JOIN strategies s ON d.strategy_id::uuid = s.id
WHERE d.status IN ('paper', 'shadow', 'partial_live', 'live')
ORDER BY d.proposed_at DESC;

-- Paper trade summary
SELECT side, COUNT(*) AS trades,
       ROUND(AVG(price)::numeric, 2) AS avg_price,
       ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) AS total_pnl
FROM paper_trades GROUP BY side;
```

---

## Quick Reference: Demo Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   45-MINUTE DEMO FLOW                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  0:00  Infrastructure Check (Docker, DB, Redis)         ──► │
│  0:05  Database Schema Walkthrough                      ──► │
│  0:10  Launch Autonomous Pipeline                       ──► │
│  0:12  Monitor Scout Network (L1) in 2nd terminal       ──► │
│  0:17  Monitor Strategy Generation (L2)                 ──► │
│  0:22  Monitor Backtesting (L3)                         ──► │
│  0:27  Monitor Validation (L3)                          ──► │
│  0:32  Monitor Risk Layer (L4)                          ──► │
│  0:35  Monitor Execution (L5) + Portfolio (L6)          ──► │
│  0:40  Monitor Meta Layer (L7) + Post-Run Summary       ──► │
│  0:45  End                                               ──► │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

*Document generated by ATLAS Pipeline Demo Guide — May 29, 2026*
*For questions, contact the ATLAS engineering team.*
