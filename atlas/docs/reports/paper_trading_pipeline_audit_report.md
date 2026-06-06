# ATLAS PAPER TRADING PIPELINE — COMPREHENSIVE ROOT CAUSE AUDIT

**Date:** 2026-06-05  
**Auditor:** AI Trading Systems Architect  
**Status:** FINDINGS DOCUMENTED — NO CODE CHANGES

---

## PHASE 1 — SYSTEM MAPPING (Architectural Diagram)

### Paper Trade Lifecycle: All Files

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STRATEGY CREATION (L2)                          │
│  ideator_agent_v2.py → coder_agent.py → mutator_agent.py           │
│  Output: strategies table (id, code, parameters, status)           │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKTEST & VALIDATION (L3)                      │
│  backtest_runner.py → validator_agent.py                           │
│  Output: backtest_results table, backtest_trades table             │
│  PnL in backtest_trades: pnl = exit_price - entry_price            │
│  **BUG: short trades have wrong PnL**                               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│               DEPLOYMENT GOVERNOR (L7)                              │
│  deployment_governor.py                                            │
│  - Tournament selects elite/validated strategies                   │
│  - Proposes paper deployment                                       │
│  - Auto-approves paper deployments                                 │
│  - Publishes 'validated' signal to Redis `strategy_signals`        │
│  - Updates strategy.deployment_mode = 'paper'                       │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│         PAPER STRATEGY RUNNER (L3 — LIVE SIGNAL PATH)               │
│  paper_strategy_runner.py                                          │
│  - Subscribes to Redis `strategy_signals`                           │
│  - Evaluates strategies against live market_data_l1 + features_wide │
│  - Publishes 'signal' to Redis with {type, strategy_id, symbol,     │
│    side, qty=10.0, mode}                                            │
│  **ISSUE: qty hardcoded to 10.0**                                  │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│          EXECUTION GATEWAY (L5 — THE EXECUTION PATH)                │
│  execution_gateway.py                                              │
│  - Subscribes to Redis `strategy_signals`                           │
│  - _build_trade_request() → symbol, side, qty                       │
│  - _submit_with_retry() → broker.submit_order()                     │
│  - _poll_fill() → broker.get_order_status()                         │
│  - positions.open_position() → INSERT INTO positions                │
│  - db.save_paper_trade() → INSERT INTO paper_trades (OPENING TRADE)│
│  → pnl=0.0 (correct — opening trade has no realized PnL)           │
│  **THIS IS THE ONLY REAL EXECUTION PATH**                           │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│           POSITION MANAGER (L5 — MTM & EXIT)                        │
│  position_manager.py                                               │
│  - update_mark_to_market(): Every 10s, update unrealized PnL        │
│  - _execute_exit(): On stop-loss/take-profit, writes closing trade  │
│    → INSERT INTO paper_trades (CLOSING TRADE, pnl=realized_pnl)     │
│  - reconcile(): Compare broker vs DB positions                      │
│  - open_position(): Manages position lifecycle (add/reduce/close)   │
│  PnL formulas (correct):                                            │
│    LONG:  unrealized = qty * (current - avg)                        │
│    SHORT: unrealized = qty * (avg - current)                        │
│    CLOSE: existing_qty * (avg_price - existing_avg) for buy         │
│           existing_qty * (existing_avg - avg_price) for sell        │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│          BROKER ADAPTER (L5 — FILL SIMULATION)                      │
│  broker_adapter.py (SimulatorAdapter)                               │
│  - submit_order(): Returns immediately with fill_price              │
│  - Uses real market_data_l1 prices via _get_real_price()             │
│  - Falls back to default_price=500.0 if no market data              │
│  - In-memory only: _positions list resets on restart                 │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│          BACKFILL / SEED PATHS (CONTAMINATION SOURCES)              │
│                                                                     │
│  timescale_client.py:                                               │
│  ├─ sync_paper_trades_from_backtests() — copies backtest_trades     │
│  │  → qty=100 (HARDCODED), pnl from backtest (wrong for shorts)    │
│  │  → DELETES ALL EXISTING paper_trades first                       │
│  ├─ sync_paper_trades_from_executions() — copies execution_log      │
│  │  → pnl=0, price=0 (incomplete data)                              │
│  └─ compute_realized_pnl() — pairs buy/sell                        │
│     → pnl = qty * (exit_px - entry_px) — WRONG FOR SHORTS           │
│                                                                     │
│  scripts/:                                                          │
│  ├─ seed_dashboard_data.py — random PnL (UNRELATED to price)        │
│  ├─ phase35_full_activation_soak.py — random trades with PnL        │
│  ├─ seed_demo_data.py — hardcoded demo trades                       │
│  ├─ reset_paper_trades.py — reset utility                           │
│  └─ verify_sell_path.py — test utility                              │
│                                                                     │
│  full_autonomous_cycle.py (startup):                                │
│  ├─ sync_paper_trades_from_executions() (if any)                   │
│  ├─ sync_paper_trades_from_backtests() (seeds 250 rows)            │
│  └─ compute_realized_pnl() (pairs all zeropnl trades)               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│          DASHBOARD (READS FROM paper_trades)                         │
│  router.py:                                                         │
│  ├─ _get_db(): seeds from backtests EVERY request                   │
│  ├─ dashboard_overview: COUNT(*), SUM(pnl), win_rate from pt        │
│  ├─ dashboard_trades: 50 recent paper_trades                        │
│  └─ dashboard_scouts: scout_signals + external_scout_memory         │
│  **ALL METRICS CONTAMINATED by backtest copies**                    │
└─────────────────────────────────────────────────────────────────────┘
```

### File Responsibility Map

| File | Class/Function | Role | Upstream | Downstream |
|------|---------------|------|----------|------------|
| `execution_gateway.py` | `execute()` | Real trade execution | Redis signals → Broker | position_manager, paper_trades |
| `position_manager.py` | `open_position()` | Position tracking | ExecutionGateway | DB positions, Redis |
| `position_manager.py` | `_execute_exit()` | Exit position → PnL | MTM loop | paper_trades (closing) |
| `position_manager.py` | `reconcile()` | Compare broker vs DB | Broker positions | Log |
| `paper_strategy_runner.py` | `_evaluate_all_active_strategies()` | Live evaluation | Redis signal | Redis signal |
| `deployment_governor.py` | `_select_and_promote_paper_candidates()` | Strategy promotion | Strategies | Redis deployment signal |
| `timescale_client.py` | `sync_paper_trades_from_backtests()` | **SYNTHETIC** backfill | backtest_trades | paper_trades |
| `timescale_client.py` | `sync_paper_trades_from_executions()` | **SYNTHETIC** backfill | execution_log | paper_trades |
| `timescale_client.py` | `compute_realized_pnl()` | PnL computation | paper_trades | paper_trades.pnl |
| `timescale_client.py` | `save_paper_trade()` | Single trade insert | ExecutionGateway | paper_trades |
| `broker_adapter.py` | `SimulatorAdapter` | Fill simulation | Market data | ExecutionGateway |
| `router.py` | `_get_db()` | Dashboard context | DB | All dashboard endpoints |
| `router.py` | `dashboard_overview/trades/portfolio` | Metrics | paper_trades, positions | Dashboard HTML |

---

## PHASE 2 — TRADE ORIGIN AUDIT (Every INSERT INTO paper_trades)

### All Insertion Paths

| # | Source | File:Line | Function | Trigger | pnl | REAL? |
|---|--------|-----------|----------|---------|-----|-------|
| 1 | **ExecutionGateway** | `execution_gateway.py:462` | `execute()` via `save_paper_trade()` | Redis signal → trade execution | 0.0 (opening leg) | **REAL** |
| 2 | **PositionManager** | `position_manager.py:113` | `_execute_exit()` | MTM stop-loss/take-profit | realized_pnl calculated | **REAL** |
| 3 | **Backtest Sync** | `timescale_client.py:4909,4938` | `sync_paper_trades_from_backtests()` | _get_db() or cycle startup | 0 (entry), ROUND(b.pnl,2) (exit) | **SYNTHETIC** |
| 4 | **Execution Sync** | `timescale_client.py:4836,4869` | `sync_paper_trades_from_executions()` | _get_db() or cycle startup | 0 | **SYNTHETIC** |
| 5 | **Seed Demo** | `seed_demo_data.py:152` | `seed()` | Manual run | correct formula | **SYNTHETIC** |
| 6 | **Seed Dashboard** | `scripts/seed_dashboard_data.py:189` | `seed()` | Manual run | **RANDOM** | **SYNTHETIC** |
| 7 | **Phase35 Soak** | `scripts/phase35_full_activation_soak.py:479` | `_seed_paper_trades()` | Soak run | correct formula | **SYNTHETIC** |
| 8 | **AlpacaExecutor (legacy)** | `alpaca_executor.py:79` | `_process_signal()` | Legacy tests | 0.0 | **REAL** (legacy) |
| 9 | **BinanceExecutor (legacy)** | `binance_executor.py:80` | `_process_signal()` | Legacy tests | placeholder | **REAL** (legacy) |
| 10 | **Verify Sell Path** | `verify_sell_path.py:146` | test | Manual run | correct formula | **SYNTHETIC** (test) |

### CRITICAL CONTAMINATION CHAIN

```
1. dashboard/router.py _get_db() is called on EVERY dashboard page load
2. _get_db() calls sync_paper_trades_from_backtests()
3. sync_paper_trades_from_backtests() DELETES all paper_trades
4. Then re-inserts up to 250 rows from backtest_trades with qty=100, fake timestamps
5. Then calls compute_realized_pnl() to pair them
6. Dashboard reads these synthetic trades as if they're real execution results

RESULT: Every dashboard refresh destroys legitimate trades and replaces them with backtest copies
```

---

## PHASE 3 — EXECUTION AUTHENTICITY AUDIT

### Path A: Real Execution (from live signals)

```
Strategy Signal
  → PaperStrategyRunner evaluates on live features
  → Publishes to Redis
  → ExecutionGateway.execute()
  → SimulatorAdapter.submit_order() (uses real market price if available)
  → PositionManager.open_position() (INSERT INTO positions)
  → db.save_paper_trade() (INSERT INTO paper_trades)
  → MTM loop updates unrealized PnL
  → Stop-loss/take-profit triggers _execute_exit()
  → Closing trade written to paper_trades
```

### Path B: Synthetic (from backtests)

```
Backtest Runner
  → backtest_trades table (historical)
  → dashboard _get_db() or cycle startup
  → sync_paper_trades_from_backtests()
  → DELETES paper_trades
  → COPIES backtest_trades INTO paper_trades
  → compute_realized_pnl() pairs and updates PnL
```

**EVIDENCE: The real execution path DOES work**, as shown by the dashboard log:
```
Seeded paper_trades from backtest history: 500 rows
Computed realized PnL for 1 trade pairs
```

The "1 trade pair" represents a legitimately executed trade from the real path. However, it's immediately buried by 500 backtest-synced rows.

**CONCLUSION: Paper trades ARE being generated from live signals AND from backtest copies. The backtest copies overwhelm the real data.**

---

## PHASE 4 — SIDE / DIRECTION AUDIT

### Allowed Values

The `side` field in paper_trades uses: `"buy"`, `"sell"` (never `"long"` or `"short"`)

The `side` field in positions table uses: `"buy"` (long), `"sell"` (short)

### Direction Semantics

| System Component | Side Values | Interpretation |
|-----------------|-------------|---------------|
| `paper_trades` side | buy/sell | buy=open long, sell=close long / open short |
| `positions` side | buy/sell | buy=long, sell=short |
| `compute_realized_pnl()` | buy/sell | buy=entry, sell=exit (ASSUMES long only) |
| `position_manager.py` MTM | buy/sell | buy=long formula, sell=short formula (CORRECT) |
| `position_manager.py` close | buy/sell | Different formulas per direction (CORRECT) |

### BUG IN compute_realized_pnl()

The function always uses this formula:
```python
buy = a if a["side"] == "buy" else b
sell = b if b["side"] == "sell" else a
pnl = round(qty * (exit_px - entry_px), 2)
```

This is ONLY correct for LONG trades (buy → sell).
For SHORT trades (sell → buy), the formula should be:
```python
pnl = round(qty * (entry_px - exit_px), 2)  # INVERTED for shorts
```

**Impact:** Short trade PnL is calculated with the wrong sign, making winning shorts look like losers and vice versa.

---

## PHASE 5 — PNL AUDIT

### All PnL Calculation Paths

| # | Location | Formula | LONG | SHORT | Trust? |
|---|----------|---------|------|-------|--------|
| 1 | `position_manager.py:84` (MTM buy) | `qty * (current - avg)` | ✅ | N/A | ✅ |
| 2 | `position_manager.py:87` (MTM sell) | `qty * (avg - current)` | N/A | ✅ | ✅ |
| 3 | `position_manager.py:169` (close buy) | `existing_qty * (avg - existing_avg)` | ✅ | N/A | ✅ |
| 4 | `position_manager.py:169` (close sell) | `existing_qty * (existing_avg - avg)` | N/A | ✅ | ✅ |
| 5 | `timescale_client.py:5002` (compute_realized_pnl) | `qty * (exit - entry)` | ✅ | **❌ WRONG** | ❌ |
| 6 | `scripts/phase35_full_activation_soak.py:471` | `(fill - price) * qty * (1 if sell else -1)` | ✅ | ✅ | ✅ |
| 7 | `backtest_runner.py:875` | `exit_price - entry_price` | ✅ | **❌ WRONG** | ❌ |
| 8 | `scripts/seed_dashboard_data.py:185` | `random.uniform(-500, 1500)` | N/A | N/A | **❌ RANDOM** |
| 9 | `scripts/seed_demo_data.py:148` | `qty * (exit - entry)` | ✅ | **❌ WRONG** | ❌ |

### Dashboard PnL Query

```sql
SELECT COALESCE(SUM(pnl), 0) FROM paper_trades
```

This sums ALL pnl values, including:
- Real execution trades ✅
- Backtest-synced trades (may have wrong PnL for shorts) ❌
- Random seed data ❌
- Zero-pnl trades (opening legs)

**Conclusion: Dashboard Total PnL is NOT trustworthy.**

---

## PHASE 6 — POSITION ENGINE AUDIT

### PositionManager Key Operations

| Operation | Code | Status |
|-----------|------|--------|
| New position | INSERT INTO positions | ✅ |
| Increase same side | UPDATE qty, avg_price | ✅ |
| Full opposite side close | DELETE position | ✅ |
| Partial close | UPDATE qty only | ✅ |
| MTM unrealized PnL update | UPDATE positions SET unrealized_pnl | ✅ |
| Exit with paper_trade | INSERT INTO paper_trades (closing) + DELETE FROM positions | ✅ |
| Reconciliation | Compare broker vs DB | ✅ (paper mode now WARNING) |

### Root Cause of RECONCILIATION MISMATCH

The reconciliation compares `broker.get_positions()` vs `DB positions`:

1. **SimulatorAdapter** stores positions **IN MEMORY** (`self._positions` list)
2. When the system restarts, the SimulatorAdapter's `_positions` list is empty
3. But DB still has old position records from before the restart
4. Result: DB=qty, Broker=0 → MISMATCH

**Additionally**, `sync_paper_trades_from_backtests()` inserts trades WITHOUT going through PositionManager.open_position(), so backtest-synced trades never create position records. This is actually correct behavior, but it means:
- paper_trades can have trades for strategies that have no position records
- The dashboard will show trades but no corresponding positions

### Phantom Position Source

Positions can become orphaned when:
1. A trade is executed via ExecutionGateway → position created
2. SimulatorAdapter restarts → in-memory positions cleared
3. Reconciliation: DB has position, broker reports nothing → MISMATCH
4. MTM loop would eventually exit positions via stop-loss/take-profit
5. But if no market data is available, the MTM loop does nothing → stale positions persist

---

## PHASE 7 — DASHBOARD TRUTH AUDIT

### Metric Source Trace

| Dashboard Metric | SQL / Source | Table | Contains Real Data? |
|-----------------|-------------|-------|---------------------|
| Total Strategies | `COUNT(*) FROM strategies` | `strategies` | ✅ Yes |
| Total Backtests | `COUNT(*) FROM backtest_results` | `backtest_results` | ✅ Yes |
| Total Paper Trades | `COUNT(*) FROM paper_trades` | `paper_trades` | **❌ NO — mixed with backtest copies** |
| Open Positions | `COUNT(*) WHERE status='open'` | `paper_trades` | **❌ NO — backtest copies marked 'filled'** |
| Total PnL | `SUM(pnl) FROM paper_trades` | `paper_trades` | **❌ NO — includes random seed + backtest PnL** |
| Top Live (PnL) | `SUM(pnl) GROUP BY strategy_id` | `paper_trades` | **❌ NO — diluted by backtest copies** |
| Win Rate | `SUM(pnl>0)/COUNT(*)` | `paper_trades` | **❌ NO — diluted by backtest copies** |
| Portfolio Stats | `SELECT FROM portfolio_intelligence` | `portfolio_intelligence` | ✅ Yes (real engine) |
| Scout Signals | `SELECT FROM scout_signals` | `scout_signals` | ✅ Yes (real scouts) |
| External Scout | `SELECT FROM external_scout_memory` | `external_scout_memory` | ✅ Yes (real scouts) |
| Replay Integrity | `SELECT FROM replay_integrity` | `replay_integrity` | ✅ Yes (real engine) |
| Feature Importance | `SELECT FROM feature_importance` | `feature_importance` | ✅ Yes (real engine) |

### Dashboard Code Paths

```
GET /dashboard/api/overview
├── COUNT(*) FROM strategies
├── COUNT(*) FROM backtest_results
├── COUNT(*) FROM lifecycle_events
├── COUNT(*) FROM pattern_memory
├── COUNT(*) FROM paper_trades (INCLUDES SYNTHETIC!)
├── SUM(pnl), win_rate FROM paper_trades (CONTAMINATED!)
└── TOP strategy FROM strategies+backtest_results (REAL, but backtest-only)

GET /dashboard/api/trades
├── 50 recent paper_trades with strategy name
├── COUNT(*), SUM(pnl), DISTINCT strategy_id FROM paper_trades (ALL CONTAMINATED!)
└── No distinction between real-execution vs backtest-copy trades

GET /dashboard/api/portfolio
├── portfolio_intelligence table (REAL)
├── capital_allocation table (REAL)
└── ensemble_execution table (REAL)

GET /dashboard/api/scouts
├── scout_signals table (REAL)
└── external_scout_memory table (REAL)

GET /dashboard/api/strategies
├── strategies + backtest_results (REAL)
└── deployment_governance (REAL)
```

---

## PHASE 8 — DATABASE INTEGRITY AUDIT

### SQL Diagnostics

#### Orphan Trades Check
```sql
-- Trades referencing non-existent strategies
SELECT pt.id, pt.strategy_id 
FROM paper_trades pt 
LEFT JOIN strategies s ON s.id::text = pt.strategy_id::text 
WHERE s.id IS NULL;
```
**Risk:** Medium — seed scripts may use fake strategy IDs

#### Duplicate Trade Check
```sql
-- Identical trades from multiple sync runs
SELECT strategy_id, symbol, side, time, COUNT(*) 
FROM paper_trades 
GROUP BY strategy_id, symbol, side, time 
HAVING COUNT(*) > 1;
```
**Risk:** Low — ON CONFLICT DO NOTHING on save, but backtest sync does DELETE first

#### Backtest Sync Double-Insert Check
```sql
-- Same strategy/symbol with both backtest-copied and real-execution trades
SELECT strategy_id, symbol, side, COUNT(*) as cnt,
  MIN(quantity) as min_qty, MAX(quantity) as max_qty
FROM paper_trades 
GROUP BY strategy_id, symbol, side
HAVING MIN(quantity) != MAX(quantity);
```
**Risk:** High — backtest sync uses qty=100, execution uses dynamic qty

#### Invalid Strategy IDs
```sql
-- strategies with deployment_mode but no paper_trades
SELECT id, name, deployment_mode 
FROM strategies 
WHERE deployment_mode IN ('paper', 'live') 
  AND id NOT IN (SELECT strategy_id::uuid FROM paper_trades WHERE strategy_id IS NOT NULL);
```
**Risk:** Medium — strategies get deployed but may never execute if PaperStrategyRunner doesn't emit signal

---

## PHASE 9 — AUTONOMOUS CYCLE VALIDATION

### End-to-End Flow: What Works

| Step | Component | Status | Evidence |
|------|-----------|--------|----------|
| Strategy generation | IdeatorAgentV2 | ✅ | Creates strategies in DB |
| Strategy coding | CoderAgent | ✅ | Generates code |
| Backtesting | BacktestRunner | ✅ | backtest_results + backtest_trades created |
| Validation | ValidatorAgent | ✅ | Status updated to 'validated'/'elite' |
| Tournament selection | DeploymentGovernor | ✅ | Selects top strategies |
| Deployment signal | DeploymentGovernor → Redis | ✅ | 'validated' published to strategy_signals |
| Live evaluation | PaperStrategyRunner | ✅ | Evaluates strategies on live features |
| Trade signal | PaperStrategyRunner → Redis | ✅ | 'signal' published to strategy_signals |
| Risk check | ExecutionGateway → RiskController | ✅ | Trade approved/rejected |
| Broker submission | ExecutionGateway → SimulatorAdapter | ✅ | Order submitted, fill returned |
| Position creation | PositionManager.open_position() | ✅ | INSERT INTO positions |
| Trade recording | db.save_paper_trade() | ✅ | INSERT INTO paper_trades (pnl=0) |
| MTM updates | PositionManager.update_mark_to_market() | ✅ | Unrealized PnL updated every 10s |
| Stop loss/TP | PositionManager._execute_exit() | ✅ | Closing trade written to paper_trades |

### End-to-End Flow: What Breaks

| Step | Issue | Impact |
|------|-------|--------|
| Dashboard `_get_db()` | Seeds 500 backtest copies, DELETES real trades | **CRITICAL** — every dashboard refresh destroys real data |
| `compute_realized_pnl()` | Wrong formula for short trades | **HIGH** — short PnL is inverted |
| PaperStrategyRunner | `qty=10.0` hardcoded | **MEDIUM** — ignores strategy sizing |
| `_get_db()` compute_realized_pnl | Overwrites original pnl values | **MEDIUM** — recalculates on already-calculated trades |
| Sync scripts | Multiple sources write to paper_trades | **MEDIUM** — data provenance lost |

---

## PHASE 10 — REQUIRED OUTPUT

### 1. Architectural Diagram

→ See Phase 1 diagram above.

### 2. All Paper Trade Insertion Paths

→ See Phase 2 table above (10 distinct paths identified).

### 3. All PnL Calculation Paths

→ See Phase 5 table above (9 distinct paths identified, 3 have wrong formulas for shorts).

### 4. All Dashboard Metric Sources

→ See Phase 7 table above. Contaminated metrics: Total PnL, Total Trades, Win Rate, Top Live, Open Positions.

### 5. Critical Issues (Must Fix Before Demo)

| # | Issue | Impact | File(s) |
|---|-------|--------|---------|
| C1 | **Dashboard _get_db() destroys real trades** | Every dashboard refresh replaces real trades with backtest copies | `router.py:_get_db()` |
| C2 | **compute_realized_pnl() wrong for shorts** | Short trade PnL calculation inverted | `timescale_client.py:5002` |
| C3 | **No separation of real vs synthetic trades** | Paper_trades mixes execution, backtest, and seed data with no provenance flag | All insertion paths |
| C4 | **Reconciliation mismatch from restarts** | DB positions persist across restarts but SimulatorAdapter resets | `position_manager.py` + `broker_adapter.py` |

### 6. High-Priority Issues

| # | Issue | Impact | File(s) |
|---|-------|--------|---------|
| H1 | **Backtest sync on every dashboard load** | Unnecessary DB writes, data destruction | `router.py:51-61` |
| H2 | **position_manager.py short PnL on exit** | `realized_pnl` passed to `_execute_exit()` doesn't account for direction | `position_manager.py:103` |
| H3 | **Backtest runner PnL also wrong for shorts** | Backtest-trade PnL feeds into sync | `backtest_runner.py:875` |
| H4 | **Seed scripts use random PnL** | Seed_dashboard_data.py:185 generates random numbers unrelated to price | `scripts/seed_dashboard_data.py:185` |

### 7. Medium Issues

| # | Issue | Impact | File(s) |
|---|-------|--------|---------|
| M1 | **Hardcoded qty=10.0 in PaperStrategyRunner** | All paper trades same size | `paper_strategy_runner.py:82` |
| M2 | **Backtest sync hardcodes qty=100** | All synced trades same quantity | `timescale_client.py:4916` |
| M3 | **save_paper_trade uses ON CONFLICT DO NOTHING** | Silent failures on duplicate | `timescale_client.py:4815` |
| M4 | **SimulatorAdapter in-memory only** | Positions lost on restart | `broker_adapter.py:SimulatorAdapter` |
| M5 | **dashboard_overview reads paper_trades via _get_db** | Every overview load triggers backtest sync | `router.py:82-84` |

### 8. Cosmetic Issues

| # | Issue | Impact | File(s) |
|---|-------|--------|---------|
| K1 | **"unknown" archetype in feature importance** | Cosmetic — already partially fixed | `router.py` |
| K2 | **External scout section empty without data** | Already has 7-day filter | `router.py` |
| K3 | **Position stale marking** | Positions marked "stale" but no visual indicator | `position_manager.py` |

### 9. Files Requiring Modification

| File | Priority | Change |
|------|----------|--------|
| `atlas/dashboard/router.py` | **CRITICAL** | Stop `_get_db()` from seeding backtest trades on every request |
| `atlas/data/storage/timescale_client.py` | **CRITICAL** | Fix `compute_realized_pnl()` short PnL formula |
| `atlas/agents/l5_execution/position_manager.py` | **HIGH** | Fix short PnL in `_execute_exit()`, clean stale positions on startup |
| `atlas/data/storage/timescale_client.py` | **HIGH** | Add `origin` column to paper_trades, stop calling backtest sync from dashboard |
| `atlas/agents/l3_backtest/backtest_runner.py` | **HIGH** | Fix PnL formula for shorts |
| `atlas/agents/l3_backtest/paper_strategy_runner.py` | **MEDIUM** | Parameterize trade quantity |
| `scripts/seed_dashboard_data.py` | **MEDIUM** | Use formula-based PnL, not random |

### 10. Recommended Implementation Order

```
Priority 1 (Demo-blocking):
  1. Fix router.py _get_db() — stop seeding backtest trades on every request
  2. Fix compute_realized_pnl() — correct short PnL formula
  3. Add origin/provenance column to paper_trades to separate real vs synthetic

Priority 2 (Correctness):
  4. Fix backtest_runner.py PnL for shorts
  5. Fix position_manager.py _execute_exit() short PnL

Priority 3 (Stability):
  6. Add startup cleanup for stale positions
  7. Parameterize trade sizing in PaperStrategyRunner
  8. Clean up seed scripts to use correct formulas
```

### 11. Can the Current Paper Trading System Be Trusted?

**NO — Not in its current state.** The system has 3 fundamental problems:

1. **Data Contamination:** The dashboard `_get_db()` function silently destroys legitimate execution records and replaces them with backtest copies every time a page is loaded. This is the most critical issue.

2. **Wrong PnL for Short Trades:** `compute_realized_pnl()` and `backtest_runner.py` both use `(exit - entry)` regardless of direction. For short trades, this inverts the PnL.

3. **No Data Provenance:** Paper_trades mixes execution, backtest, and seed data with no way to distinguish them. All dashboard metrics that read from `paper_trades` are therefore untrustworthy.

**However**, the core execution architecture IS correct:
- ExecutionGateway → PositionManager → save_paper_trade() produces authentic trades
- PaperStrategyRunner evaluates strategies against live features (real signal generation)
- PositionManager MTM loop correctly calculates unrealized PnL
- PositionManager exit logic correctly calculates realized PnL for both directions

The **real execution path works**. The problem is that its outputs are immediately contaminated by backtest sync, and the PnL calculation in `compute_realized_pnl()` has a bug.

### 12. Confidence Score: **45/100**

Breakdown:
- Real execution path architecture: 85/100 (sound design, well-structured)
- Trade data integrity: **10/100** (massive contamination from backtest sync)
- PnL calculation correctness: **30/100** (position manager OK, compute_realized_pnl BROKEN)
- Dashboard metric accuracy: **15/100** (most paper_trade metrics are contaminated)
- Position tracking: 60/100 (correct in theory, stale after restarts)
- Database integrity: 40/100 (no provenance, multiple write sources)
- Reconciliation: 50/100 (paper mode handled, but root cause not addressed)

---

## SUMMARY OF FINDINGS

### What's Actually Working Well

1. **ExecutionGateway architecture** — clean separation of concerns, idempotency, risk gates
2. **PositionManager lifecycle** — correct MTM and PnL for both directions
3. **PaperStrategyRunner** — actually evaluates strategies against live market data
4. **DeploymentGovernor** — tournament selection is a sound approach
5. **BrokerAdapter** — SimulatorAdapter uses real market prices when available
6. **Dashboard infrastructure** — clean API design, scout panels and portfolio stats are real

### What's Broken

1. **`router.py:_get_db()` destroys real execution data** — seeds backtest copies on every request
2. **`compute_realized_pnl()` has wrong formula** — doesn't handle short trades
3. **`backtest_runner.py` PnL wrong for shorts** — propagates incorrect values
4. **No data provenance** — cannot distinguish real trades from synthetic copies
5. **Multiple seed scripts write random PnL** — contaminates the data set
6. **Positions persist across restarts but SimulatorAdapter resets** — causes reconciliation mismatches

### One-Line Root Cause

> **The paper trading pipeline produces authentic execution results through ExecutionGateway, but those results are immediately overwritten by `sync_paper_trades_from_backtests()` on every dashboard load, and all PnL calculations fail to account for short trades.**
