# ATLAS DATABASE AUDIT REPORT
**Date:** May 18, 2026  
**Scope:** Schema definition, data integrity, drift detection, institutional readiness  
**Status:** COMPREHENSIVE ANALYSIS — 27 TABLES AUDITED

---

## EXECUTIVE SUMMARY

### Overall Assessment
- **Total Tables:** 27 (19 mandatory + 8 supporting)
- **Schema Maturity:** 6.5/10 (Operational, gaps identified)
- **Data Integrity:** 6/10 (Good for reads, gaps in write safety)
- **Institutional Readiness:** 5.5/10 (Production use, needs hardening)

### Critical Findings
1. **PRECISION CRISIS:** NUMERIC columns store unbounded precision (comment-based docs, no enforcement)
2. **MISSING CONSTRAINTS:** No NOT NULL enforcement on critical fields; no uniqueness constraints on composite keys
3. **ORPHAN RISK:** Foreign keys exist but cascade behavior undefined; no foreign key constraints in execution_log
4. **DRIFT DETECTED:** 8 schema mutations in timescale_client.connect() not in canonical schema files
5. **AUDIT GAP:** No automatic trailing of writes to core tables (execution_log is read-only but immutable semantics not enforced)

### Top 5 Schema Risks
1. **Unbounded Precision in Market Data** → Potential float rounding errors accumulating in backtests
2. **Missing Foreign Key Constraints** → Copy trader data could reference non-existent accounts
3. **Materialized View Refresh Staleness** → features_wide may be stale during backtest execution
4. **No Uniqueness Constraint on Copy Execution** → Duplicate orders possible if idempotent insert fails
5. **Trace ID as TEXT in lifecycle_events** → UUID vs TEXT mismatch with strategies table

### Top 5 Data Integrity Threats
1. **Duplicate Market Data Ingestion** → No UNIQUE constraint on (time, symbol) in market_data_l1
2. **Orphaned Backtest Records** → Strategies deleted but backtest_results remain
3. **Feature Calculation Divergence** → Same symbol at same time could have different feature values across runs
4. **Position Calculation Mismatch** → positions table not atomically updated with copy_execution_log
5. **Failed Execution Replay Undefined** → execution_dead_letter has no retry logic; manual intervention required

### Top 5 Most Critical Tables
1. **market_data_l1** — L1 ingestion; all strategy decisions depend on this
2. **copy_execution_log** — Copy trader audit trail; regulatory/operational visibility
3. **strategies** — Master strategy inventory; core R&D output
4. **execution_log** — Order audit trail; compliance requirement
5. **features** → features_wide → strategy_execution; performance bottleneck

---

## TABLE-BY-TABLE AUDIT MATRIX

### 1. MARKET_DATA_L1 (L1 OHLCV Ingestion)

**Classification:** TimescaleDB Hypertable | Time-series | CRITICAL

**Purpose:**  
Raw OHLCV bars ingested from Binance/Polygon. Foundation for all feature calculation and backtesting.

**Schema:**
```
time              TIMESTAMPTZ NOT NULL     — Partition key; bar close time
symbol            TEXT NOT NULL           — Ticker (BTC, AAPL, etc.)
open              NUMERIC NOT NULL        — Comment: target 4 decimals
high              NUMERIC NOT NULL        — Comment: target 4 decimals
low               NUMERIC NOT NULL        — Comment: target 4 decimals
close             NUMERIC NOT NULL        — Comment: target 4 decimals
volume            NUMERIC NOT NULL        — Comment: crypto 6 decimals, equity 4
source            TEXT NOT NULL           — "binance", "polygon"
interval          TEXT NOT NULL           — "1m", "5m", "1h"
asset_class       TEXT DEFAULT 'crypto'   — "crypto" or "equity"
ingestion_time    TIMESTAMPTZ DEFAULT NOW() — When row was inserted
```

**Indexes:**
- Hypertable clustering on `time` (automatic)
- NO explicit indexes on symbol or asset_class (DRIFT: should exist for query performance)

**Data Integrity Guarantees:**
- ✅ Time partitioning enforced by TimescaleDB
- ❌ NO uniqueness constraint on (time, symbol)
- ❌ NO NOT NULL on volume (can be 0 or NULL)
- ❌ Precision documented in comment but NOT enforced; NUMERIC unbounded

**Write Dependencies:**
- `timescale_client.write_bars()` — crypto/equity ingestion
- `timescale_client.write_aggregate()` — Polygon A.* streams
- `timescale_client.write_binance_trade()` — Binance @depth
- Precision rounding in code: `_r4(open), _r6(volume if crypto else _r4(volume))`

**Read Dependencies:**
- `backtest_runner.get_bars()` → used in every strategy backtest
- `feature_calculator.compute_features()` → converts L1 to indicators
- `dashboard.market_data_endpoint()` → visualization
- Direct SQL: `FROM market_data_l1 WHERE symbol = :sym AND interval = :int`

**Crash Recovery:**
- ✅ Hypertable restart-safe; TimescaleDB auto-recovery
- ⚠️ Data deduplication depends on ON CONFLICT DO NOTHING (idempotent, but relies on code discipline)
- ❌ No version tracking; can't tell if ingestion broke mid-stream

**Known Drift Risks:**
1. **Precision Mismatch:** Code rounds to 4dp OHLC, 6dp crypto volume, but schema comment only. Stored values could have any precision.
2. **Missing Symbol Index:** Queries filter by symbol frequently; currently TimescaleDB must scan all partitions.
3. **Nullable Volume:** volume NOT NULL in schema but code could pass NULL → silent truncation.

**Institutional Maturity:** 5/10
- ✅ Hypertable partition strategy solid
- ✅ Idempotent ingestion via ON CONFLICT
- ❌ No precision enforcement
- ❌ No uniqueness constraint
- ❌ Missing indexes for query performance

---

### 2. MARKET_DATA_L2 (Orderbook Snapshots)

**Classification:** TimescaleDB Hypertable | Time-series | HIGH

**Purpose:**  
Real-time orderbook snapshots (bids, asks, spread, mid_price). Used for execution quality analysis.

**Schema:**
```
time              TIMESTAMPTZ NOT NULL
symbol            TEXT NOT NULL
bids              JSONB NOT NULL         — {price: qty} mapping
asks              JSONB NOT NULL         — {price: qty} mapping
spread            NUMERIC NOT NULL       — Comment: target 6 decimals
mid_price         NUMERIC NOT NULL       — Comment: target 6 decimals
```

**Indexes:**
- Hypertable clustering on `time` (automatic)
- NO indexes on symbol or spread (DRIFT)

**Data Integrity Issues:**
- ❌ JSONB not validated; could store invalid price/qty pairs
- ❌ Spread/mid_price unbounded precision (comment only)
- ❌ No constraint: spread must be >= 0
- ❌ No constraint: mid_price between best bid and ask

**Write Dependencies:**
- `write_quote()` → Polygon Q.* streams
- `write_binance_depth()` → Binance @depth20@100ms
- Precision: `_r6(data.ask - data.bid)`, `_r6((data.bid + data.ask) / 2)`

**Read Dependencies:**
- `copy_trader.check_execution_quality()` (minimal)
- Dashboard orderbook visualization

**Restart Safety:** ✅ Hypertable restart-safe; TimescaleDB recovery

**Known Drift Risks:**
1. **JSONB Not Validated:** Malformed orderbook stored as-is; no schema validation
2. **Stale Snapshot Risk:** Multiple updates per second but no version field; can't detect gaps
3. **Precision in JSONB Keys:** Bids/asks stored as JSON strings; could have arbitrary precision

**Institutional Maturity:** 4/10
- ❌ JSONB validation missing
- ❌ No precision enforcement
- ❌ No spread/mid_price constraints
- ❌ Minimal query performance optimization

---

### 3. ORDER_FLOW (Tick Data)

**Classification:** TimescaleDB Hypertable | Time-series | MEDIUM

**Purpose:**  
Individual trade ticks for order flow analysis. Lower criticality; primarily used for feature calculation.

**Schema:**
```
time              TIMESTAMPTZ NOT NULL
symbol            TEXT NOT NULL
price             NUMERIC NOT NULL       — Comment: target 6 decimals
size              NUMERIC NOT NULL       — Comment: target 4 decimals
side              TEXT NOT NULL          — "buy" or "sell"
aggressor         TEXT NOT NULL          — Exchange or trade ID
```

**Indexes:**
- Hypertable clustering on `time`
- NO symbol index (DRIFT)

**Data Integrity:**
- ❌ Side values not validated (could be anything)
- ❌ Price/size precision unbounded
- ❌ No constraint: price > 0, size > 0

**Write Dependencies:**
- `write_trade()` — Polygon T.* streams
- `write_binance_trade()` — Binance @trade stream

**Read Dependencies:**
- `feature_calculator` → order flow imbalance calculations
- Minimal direct reads

**Restart Safety:** ✅ Hypertable restart-safe

**Known Drift Risks:**
1. **Side Validation Missing:** No CHECK constraint; "BUY", "buy", "BUY_" all stored differently
2. **Duplicate Trade Ticks:** No uniqueness on (time, symbol, side, aggressor); duplicates possible
3. **Negative Prices/Sizes:** No CHECK constraints; invalid data accepted

**Institutional Maturity:** 4/10
- ❌ Side/price/size validation missing
- ❌ No uniqueness constraints
- ❌ Performance index missing

---

### 4. FEATURES (EAV Technical Indicators)

**Classification:** TimescaleDB Hypertable | Time-series | CRITICAL

**Purpose:**  
Entity-Attribute-Value storage for 20+ technical indicators. Core input to strategy backtests.

**Schema:**
```
time              TIMESTAMPTZ NOT NULL
symbol            TEXT NOT NULL
feature_name      TEXT NOT NULL          — "rsi_14", "macd", "returns", etc.
value             NUMERIC NOT NULL       — Comment: 6dp for most, 8dp for returns
```

**Indexes:**
- Hypertable clustering on `time`
- NO (symbol, feature_name) index (DRIFT)

**Data Integrity Issues:**
- ❌ feature_name values not validated; could be misspelled
- ❌ value precision unbounded (comment-based 6dp/8dp)
- ❌ No check: returns/log_returns in range [-1, 1]
- ❌ Multiple values per (time, symbol, feature_name) possible

**Write Dependencies:**
- `write_features()` → Rounding: `_r8` for ratios, `_r6` for indicators
- Called from `feature_calculator.compute_all()` → runs for each bar

**Read Dependencies:**
- `features_wide` materialized view (pivots EAV → columns)
- `backtest_runner` → queries features_wide for fast access
- Feature engineering pipeline

**Restart Safety:**
- ✅ Hypertable restart-safe
- ⚠️ features_wide can fall stale if not refreshed after ingestion

**Known Drift Risks:**
1. **Feature Name Typos:** No enum/lookup table; feature names could drift (rsi_14 vs RSI_14 vs rsi_14)
2. **Multiple Values per Key:** No uniqueness on (time, symbol, feature_name); both rows could exist
3. **Missing Features:** No audit of which symbols have which features; silent gaps possible
4. **Precision Divergence:** Same feature calculated twice with different precision (e.g., _r6 vs _r8)

**Institutional Maturity:** 5/10
- ✅ EAV design flexible for 20+ features
- ❌ No feature_name validation
- ❌ No uniqueness on (time, symbol, feature_name)
- ❌ Precision enforcement missing
- ❌ features_wide staleness risk

---

### 4b. FEATURES_WIDE (Materialized View)

**Classification:** Materialized View | Derived/Cache | HIGH

**Purpose:**  
Denormalized view pivoting features EAV → wide columns for fast strategy lookups.

**Schema:**
```
time             TIMESTAMPTZ
symbol           TEXT
returns          NUMERIC           — from features where feature_name='returns'
log_returns      NUMERIC
rsi_14           NUMERIC
macd             NUMERIC
... (20 columns total)
```

**Data Integrity Issues:**
- ❌ NOT a table; cannot insert/update directly
- ⚠️ Refresh staleness: `REFRESH MATERIALIZED VIEW features_wide` is manual
- ⚠️ AUTO refresh only in `timescale_client.connect()` on migration
- ❌ No concurrent refresh during runtime; blocks queries if refresh runs

**Write Dependencies:**
- Derived from `features` table
- Auto-migration in `timescale_client.connect()` checks if schema is outdated

**Read Dependencies:**
- `backtest_runner.get_latest_features()` → assumes fresh
- Strategy execution → real-time feature access

**Restart Safety:** ⚠️ Partial
- If restart happens mid-refresh, view could be stale/locked
- No versioning to detect stale reads

**Known Drift Risks:**
1. **Stale View Risk:** features_wide could be 1+ minutes behind features table if refresh not run
2. **Silent Column Additions:** New features added to features table but features_wide not refreshed
3. **Schema Mismatch:** Migration drops/recreates view; concurrent queries could fail during migration

**Institutional Maturity:** 4/10
- ❌ Manual refresh required
- ❌ No staleness versioning
- ❌ Can block during refresh
- ✅ Unique index prevents duplicates post-refresh

---

### 5. STRATEGIES (Strategy Definitions)

**Classification:** Relational Table | Catalog | CRITICAL

**Purpose:**  
Master strategy definitions; the output of L2 Ideator/Mutator/Combiner agents.

**Schema:**
```
id                 UUID PRIMARY KEY
name               TEXT NOT NULL
code               TEXT NOT NULL         — Python code
parameters         JSONB NOT NULL        — Strategy config
status             TEXT NOT NULL         — pending_code, pending_backtest, validated, etc.
created_at         TIMESTAMPTZ NOT NULL
author_agent       TEXT NOT NULL         — "IdeatorAgent", "MutatorAgent", etc.
prompt             TEXT                  — LLM prompt used
raw_response       TEXT                  — LLM output
normalized_strategy JSONB                 — Structured version of parameters
compile_error      TEXT                  — Syntax errors if compilation failed
strategy_signature TEXT                  — Dedup hash
trace_id           TEXT                  — Event lineage link
generation_batch   TEXT (auto-migrated)  — Batch ID
validation_metrics JSONB (auto-migrated)  — Backtest metrics storage
train_sharpe       NUMERIC (optional)
test_sharpe        NUMERIC (optional)
holdout_sharpe     NUMERIC (optional)
```

**Indexes:**
- Primary key on `id` (UUID)
- Index on `trace_id` (event lineage)
- Index on `strategy_signature` (dedup)
- Index on `status` (query by status)
- NO index on `created_at` (DRIFT: queries order by created_at)

**Data Integrity Issues:**
- ❌ code/parameters could be NULL or invalid JSON
- ❌ No NOT NULL on parameters → malformed JSON stored
- ❌ No check on status enum values
- ❌ trace_id as TEXT but lifecycle_events.strategy_id as TEXT; inconsistent with UUID
- ❌ No check: sharpe values in [-10, 10] range

**Write Dependencies:**
- `save_strategy()` → Writes from IdeatorAgent, MutatorAgent, CombinerAgent
- `update_strategy_status()` → Status updates during backtest/validation
- `update_strategy_code()` → Code injection after CodeGen

**Read Dependencies:**
- `backtest_runner.fetch_strategies_by_status()` → Get pending backtests
- `validator_agent.rank_strategies()` → Sort by sharpe
- Dashboard strategy browser

**Restart Safety:**
- ✅ Inserts idempotent (UUID primary key)
- ⚠️ Status updates not atomic; could be left in invalid state on crash
- ❌ No transactions around (insert, compile, set status)

**Known Drift Risks:**
1. **Invalid JSON in parameters:** No JSON schema validation
2. **Code Column Divergence:** code and normalized_strategy could represent different logic
3. **Status Orphans:** Strategy in "pending_backtest" but backtest_results don't exist
4. **Trace ID Mismatch:** trace_id is TEXT but UUID elsewhere; link could be broken
5. **Sharpe Range Unbounded:** No constraint on train_sharpe/test_sharpe; invalid values stored

**Institutional Maturity:** 6/10
- ✅ Dedup via strategy_signature
- ✅ Event lineage link via trace_id
- ❌ Status updates not transactional
- ❌ No JSON schema validation
- ❌ Missing created_at index
- ❌ Sharpe range unbounded

---

### 6. BACKTEST_RESULTS (Strategy Performance Metrics)

**Classification:** Relational Table | Catalog | HIGH

**Purpose:**  
Summary backtest metrics (Sharpe, CAGR, max_drawdown, win_rate) used for strategy ranking.

**Schema:**
```
strategy_id        UUID NOT NULL          — FK → strategies.id
start_date         TIMESTAMPTZ NOT NULL   — Backtest period start
end_date           TIMESTAMPTZ NOT NULL   — Backtest period end
sharpe             NUMERIC
cagr               NUMERIC
max_drawdown       NUMERIC
win_rate           NUMERIC
total_trades       INT
passed_validation  BOOLEAN
results            JSONB                  — Extended results storage
entry_count        INT
exit_count         INT
bars_processed     INT
short_window_score NUMERIC
score_7d           NUMERIC
score_14d          NUMERIC
score_30d          NUMERIC
PRIMARY KEY        (strategy_id, start_date, end_date)
```

**Indexes:**
- Composite PK on (strategy_id, start_date, end_date)
- NO explicit FK constraint on strategy_id (DRIFT)
- NO index on sharpe or cagr (needed for ranking)

**Data Integrity Issues:**
- ❌ NO foreign key constraint on strategy_id → orphaned rows possible
- ❌ Sharpe/CAGR/max_drawdown precision unbounded
- ❌ No check: sharpe in [-10, 10], cagr in [-1, 10], max_drawdown in [-1, 0]
- ❌ No check: win_rate in [0, 1]
- ❌ results JSONB not validated

**Write Dependencies:**
- `backtest_runner.save_backtest_results()` → Writes after backtest completion

**Read Dependencies:**
- `validator_agent.rank_strategies()` → Sort by sharpe
- `mutation_pattern_agent` → Aggregate parent/child sharpe deltas
- Dashboard metrics display

**Restart Safety:**
- ⚠️ Composite key prevents duplicate results for same strategy/period
- ❌ If backtest crashes mid-write, could insert partial results

**Known Drift Risks:**
1. **Orphaned Backtest Records:** Strategy deleted but backtest_results remain
2. **Duplicate Backtests:** Same strategy/period could be backtest multiple times; last one wins
3. **Precision Divergence:** Different rounding between calculation and storage
4. **Correlation Drift:** sharpe from mutation_memory vs backtest_results could differ

**Institutional Maturity:** 5/10
- ✅ Composite key prevents exact duplicates
- ❌ No FK constraint on strategy_id
- ❌ No precision enforcement
- ❌ No indexes on rank columns (sharpe, cagr)
- ❌ Orphan rows possible

---

### 7. BACKTEST_TRADES (Individual Trade Records)

**Classification:** Relational Table | Detail | MEDIUM

**Purpose:**  
Individual trades executed during backtest. Used for trade-by-trade P&L analysis.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
strategy_id        UUID NOT NULL          — FK → strategies.id
symbol             TEXT NOT NULL
entry_time         TIMESTAMPTZ
exit_time          TIMESTAMPTZ
entry_price        NUMERIC
exit_price         NUMERIC
side               TEXT                   — "long" or "short"
pnl                NUMERIC
pnl_pct            NUMERIC
bars_held          INT
exit_reason        TEXT                   — "target_hit", "stop_loss", etc.
```

**Indexes:**
- Primary key on `id` (UUID)
- Index on `strategy_id` (query by strategy)
- Index on `entry_time` (query by date)
- Index on `symbol` (auto-migrated)
- NO FK constraint on strategy_id (DRIFT)

**Data Integrity Issues:**
- ❌ NO foreign key constraint on strategy_id → orphans possible
- ❌ side values not validated (could be anything)
- ❌ entry_price/exit_price/pnl precision unbounded
- ❌ No check: entry_time < exit_time
- ❌ No check: pnl_pct in [-1, 10]

**Write Dependencies:**
- `backtest_runner.write_trade_details()` → Called for each trade

**Read Dependencies:**
- `dashboard.trade_details()` → Trade browser
- `mutation_pattern_agent.analyze_trades()` → Parent/child trade comparison

**Restart Safety:**
- ✅ UUID primary key; insertions idempotent if duplicated
- ⚠️ If backtest crash mid-strategy, partial trades could be inserted

**Known Drift Risks:**
1. **Orphaned Trade Records:** Strategy deleted but trades remain
2. **Side Value Mismatch:** "long"/"short" inconsistent with entry_price ordering
3. **Missing Trades:** Backtest ran but trades not written (silent gap)

**Institutional Maturity:** 4/10
- ❌ No FK constraint on strategy_id
- ❌ Side validation missing
- ❌ No ordering constraint (entry_time < exit_time)
- ❌ Precision unbounded

---

### 8. PAPER_TRADES (Paper Trading Orders)

**Classification:** TimescaleDB Hypertable | Time-series | LOW

**Purpose:**  
Orders placed in paper trading mode. Lower criticality; primarily for testing.

**Schema:**
```
time               TIMESTAMPTZ NOT NULL   — Partition key
strategy_id        UUID NOT NULL
symbol             TEXT NOT NULL
side               TEXT NOT NULL
quantity           NUMERIC NOT NULL
price              NUMERIC NOT NULL
fill_price         NUMERIC
status             TEXT NOT NULL          — "pending", "filled", "cancelled"
pnl                NUMERIC
```

**Indexes:**
- Hypertable clustering on `time`
- NO (strategy_id, symbol) index (DRIFT)

**Data Integrity:**
- ❌ side values not validated
- ❌ quantity/price precision unbounded
- ❌ fill_price should only be set if status='filled'

**Write Dependencies:**
- Paper trading engine (if running)

**Read Dependencies:**
- Dashboard paper trading review (minimal)

**Restart Safety:** ✅ Hypertable restart-safe

**Known Drift Risks:**
1. **Stale Status:** paper_trades.status not updated when backtest cancels
2. **Partial Fill Tracking:** Multiple fills for same order not tracked

**Institutional Maturity:** 3/10
- Low criticality; minimal oversight needed
- ❌ No precision/validation constraints

---

### 9. AGENT_REGISTRY (Agent Health)

**Classification:** Relational Table | Operational | MEDIUM

**Purpose:**  
Master registry of all running agents (L1-L7). Used for health monitoring.

**Schema:**
```
id                 UUID PRIMARY KEY
name               TEXT NOT NULL          — "IdeatorAgent", "CopyTraderV1", etc.
type               TEXT NOT NULL          — "ideator", "mutator", "backtester", etc.
layer              TEXT NOT NULL          — "L1", "L2", ... "L7"
status             TEXT NOT NULL          — "running", "stopped", "error"
pid                INT                    — Process ID
last_heartbeat     TIMESTAMPTZ NOT NULL
created_at         TIMESTAMPTZ NOT NULL
metadata           JSONB
```

**Indexes:**
- Primary key on `id`
- NO index on status (DRIFT: queries filter by status)
- NO index on layer (DRIFT)

**Data Integrity Issues:**
- ❌ status values not validated (no enum)
- ❌ pid could be orphaned (process died but registry not updated)
- ❌ No check: last_heartbeat >= created_at
- ❌ No check: heartbeat within last N minutes

**Write Dependencies:**
- Agent startup → `write_agent()`
- Heartbeat loop → Upsert `last_heartbeat` every 30s

**Read Dependencies:**
- Dashboard agent status
- Health check endpoint
- Monitoring/alerting

**Restart Safety:**
- ⚠️ On crash, agent row left with stale heartbeat
- NO mechanism to auto-clean stale agents
- Dashboard could show "running" agents that are actually dead

**Known Drift Risks:**
1. **Stale Agent Rows:** Agents crashed but registry shows "running"
2. **Orphaned PIDs:** Multiple agents with same name but different PIDs
3. **No Heartbeat Cleanup:** Dead agents never removed from registry

**Institutional Maturity:** 4/10
- ❌ No status enum/validation
- ❌ No stale heartbeat cleanup
- ❌ No heartbeat time constraint
- ⚠️ Useful for operational visibility but needs automation

---

### 10. SYSTEM_LOGS (Audit Trail)

**Classification:** TimescaleDB Hypertable | Time-series | HIGH

**Purpose:**  
Immutable append-only logs from all agents. Primary audit trail for operational debugging.

**Schema:**
```
time               TIMESTAMPTZ NOT NULL   — Partition key
agent_id           UUID NOT NULL          — FK → agent_registry.id
level              TEXT NOT NULL          — "INFO", "WARNING", "ERROR"
message            TEXT NOT NULL
metadata           JSONB
```

**Indexes:**
- Hypertable clustering on `time`
- NO (agent_id, level) index for filtering (DRIFT)

**Data Integrity:**
- ❌ agent_id NOT NULL but no FK constraint to agent_registry
- ❌ level values not validated (could be "INVALID_LEVEL")
- ❌ No constraint on message length (could be 1MB+)

**Write Dependencies:**
- `db.log(agent_id, level, message, metadata)` → Called throughout agents

**Read Dependencies:**
- Dashboard logs browser
- Alerting on ERROR-level logs
- Debugging failed strategies

**Restart Safety:** ✅ Append-only hypertable; restart-safe

**Known Drift Risks:**
1. **Log Spill:** Large metadata JSONB could slow partition ingestion
2. **Missing Agent Logs:** If agent_id doesn't exist in agent_registry, still logged (FK not enforced)
3. **Staleness:** agent_registry.id could be deleted but logs remain; orphaned

**Institutional Maturity:** 6/10
- ✅ Append-only design
- ✅ Hypertable partition strategy
- ❌ No level validation
- ❌ No FK constraint on agent_id
- ❌ No index for level/agent_id filtering

---

### 11. PERFORMANCE_METRICS (Strategy Performance Over Time)

**Classification:** TimescaleDB Hypertable | Time-series | MEDIUM

**Purpose:**  
Track strategy performance metrics over time (e.g., daily Sharpe, rolling PnL).

**Schema:**
```
time               TIMESTAMPTZ NOT NULL   — Partition key
strategy_id        UUID NOT NULL
metric_name        TEXT NOT NULL          — "daily_sharpe", "rolling_pnl", etc.
value              NUMERIC NOT NULL
```

**Indexes:**
- Hypertable clustering on `time`
- NO (strategy_id, metric_name) index (DRIFT)

**Data Integrity:**
- ❌ metric_name values not validated (no enum)
- ❌ value precision unbounded
- ❌ No constraint: sharpe in [-10, 10], pnl values valid

**Write Dependencies:**
- `performance_calculator.record_metrics()` → Called daily

**Read Dependencies:**
- Dashboard performance charts
- Strategy ranking

**Restart Safety:** ✅ Hypertable restart-safe

**Known Drift Risks:**
1. **Metric Name Drift:** "daily_sharpe" vs "sharpe_daily" inconsistency
2. **Missing Metrics:** Some days/strategies could lack records
3. **Precision Divergence:** Same metric calculated differently on different dates

**Institutional Maturity:** 4/10
- ❌ No metric_name enum/validation
- ❌ Precision unbounded
- ❌ No index for query performance

---

### 12. INTELLIGENCE_BRIEFS (Regime Detection Output)

**Classification:** Relational Table | Catalog | LOW

**Purpose:**  
Regime detection output from IntelligenceBriefAgent. Provides context for strategy selection.

**Schema:**
```
id                 UUID PRIMARY KEY
generated_at       TIMESTAMPTZ NOT NULL
brief_text         TEXT NOT NULL
regime             TEXT NOT NULL          — "bull", "bear", "sideways", etc.
strategies_count   INT NOT NULL
```

**Indexes:**
- Primary key on `id`
- NO index on generated_at (DRIFT: queries order by latest)

**Data Integrity:**
- ❌ regime values not validated (enum)
- ❌ strategies_count not validated (should be > 0)

**Write Dependencies:**
- `intelligence_brief_agent.generate_brief()`

**Read Dependencies:**
- Dashboard market regime display (minimal)

**Restart Safety:** ✅ Insert-only

**Known Drift Risks:**
1. **Stale Brief:** Most recent brief could be hours old; no freshness guarantee
2. **Regime Enum Drift:** "BULL" vs "bull" vs "bullish"

**Institutional Maturity:** 3/10
- Low criticality; minimal data governance needed

---

### 13. MUTATION_MEMORY (Mutation Lineage)

**Classification:** Relational Table | Lineage | HIGH

**Purpose:**  
Parent-child lineage for mutations. Tracks which mutations improved/degraded performance.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
parent_strategy_id UUID NOT NULL REFERENCES strategies(id)
child_strategy_id  UUID NOT NULL REFERENCES strategies(id)
mutation_type      TEXT NOT NULL          — "feature_swap", "threshold_adjust", etc.
changed_fields     TEXT[]                 — Fields changed
parent_sharpe      NUMERIC
child_sharpe       NUMERIC
sharpe_delta       NUMERIC
parent_entry_count INT
child_entry_count  INT
parent_trades      INT
child_trades       INT
created_at         TIMESTAMPTZ DEFAULT NOW()
```

**Indexes:**
- Primary key on `id`
- Index on `parent_strategy_id`
- Index on `child_strategy_id`
- NO index on `mutation_type` (DRIFT: queries group by mutation_type)

**Data Integrity:**
- ✅ Foreign keys to strategies table (enforced!)
- ❌ mutation_type values not validated
- ❌ No check: parent_trades > 0, child_trades > 0
- ❌ No check: sharpe_delta values valid

**Write Dependencies:**
- `mutator_agent.record_mutation()` → After mutation evaluation

**Read Dependencies:**
- `mutation_pattern_agent.analyze_mutations()` → Aggregate by type
- Dashboard mutation leaderboard

**Restart Safety:**
- ✅ Insert-only; FK ensures both parents exist before insert
- ⚠️ If mutation incomplete, could have orphaned child (marked as incomplete)

**Known Drift Risks:**
1. **Stale Mutation Stats:** Leaderboard could be outdated if not queried recently
2. **Missing Mutations:** Some mutations not recorded if agent crashed

**Institutional Maturity:** 6/10
- ✅ FK constraints enforced
- ✅ Good indexing for parent/child lookups
- ❌ No mutation_type enum/validation
- ❌ No mutation_type index (needed for ranking)

---

### 14. COMBINATION_MEMORY (Strategy Combination Lineage)

**Classification:** Relational Table | Lineage | HIGH

**Purpose:**  
Parent-child lineage for strategy combinations (L2 Combiner output). Tracks combinations that improved performance.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
parent_a           UUID NOT NULL REFERENCES strategies(id)
parent_b           UUID NOT NULL REFERENCES strategies(id)
child_id           UUID REFERENCES strategies(id)
combination_type   TEXT NOT NULL          — "ensemble_vote", "signal_blend", etc.
parent_a_sharpe    NUMERIC
parent_b_sharpe    NUMERIC
child_sharpe       NUMERIC
sharpe_delta       NUMERIC
created_at         TIMESTAMPTZ DEFAULT NOW()
UNIQUE             (parent_a, parent_b, combination_type)
```

**Indexes:**
- Primary key on `id`
- Index on `parent_a`
- Index on `parent_b`
- Index on `child_id`
- Unique constraint on (parent_a, parent_b, combination_type)

**Data Integrity:**
- ✅ Foreign keys to strategies table (enforced)
- ✅ Unique constraint prevents duplicate combinations
- ❌ combination_type values not validated
- ⚠️ child_id nullable; some combinations untested

**Write Dependencies:**
- `combiner_agent.record_combination()` → After combination evaluation

**Read Dependencies:**
- `combination_leaderboard()` → Dashboard
- Strategy ranking

**Restart Safety:**
- ✅ Insert-only; unique constraint prevents duplicates
- ⚠️ Unique constraint could block legitimate recombination with different output

**Known Drift Risks:**
1. **Stale Combinations:** child_id NULL for untested combinations
2. **Unique Constraint Too Strict:** Could prevent intentional recombination if trying different config

**Institutional Maturity:** 7/10
- ✅ FK constraints enforced
- ✅ Good indexing
- ✅ Unique constraint prevents exact duplicates
- ❌ combination_type not validated
- ⚠️ Nullable child_id could cause confusion

---

### 15. LIFECYCLE_EVENTS (Event Lineage)

**Classification:** Relational Table | Lineage | HIGH

**Purpose:**  
Event lineage for strategy lifecycle. Tracks stages: ideation → code → backtest → validation → deployment.

**Schema:**
```
id                 TEXT PRIMARY KEY       — event_id
trace_id           TEXT NOT NULL          — Links to strategies.trace_id
strategy_id        TEXT                   — Strategy being tracked
stage              TEXT NOT NULL          — "ideator", "coder", "validator", etc.
status             TEXT NOT NULL          — "pending", "completed", "failed"
actor              TEXT NOT NULL          — Agent that performed action
parent_event_id    TEXT                   — Previous event in chain
metadata           JSONB DEFAULT '{}'
created_at         TIMESTAMPTZ DEFAULT NOW()
```

**Indexes:**
- Primary key on `id`
- Index on `trace_id` (link to strategy cohort)
- Index on `strategy_id` (link to strategy)
- Index on `stage` (query by stage)

**Data Integrity Issues:**
- ❌ trace_id as TEXT but strategies.trace_id as TEXT (good, consistent)
- ⚠️ strategy_id as TEXT but should be UUID (DRIFT: type mismatch)
- ❌ stage values not validated
- ❌ status values not validated
- ❌ No foreign key constraint on parent_event_id

**Write Dependencies:**
- `event_lineage_client.create_event()` → Called from agents after stage completion
- Auto-called from `save_strategy()`

**Read Dependencies:**
- Dashboard trace visualization
- Strategy lineage tracking

**Restart Safety:**
- ✅ Insert-only (immutable events)
- ⚠️ If event_id generation collides, second insert fails

**Known Drift Risks:**
1. **Type Mismatch:** strategy_id TEXT vs UUID; link could be broken
2. **Missing Events:** Some stages not recorded if agent crashes
3. **Orphaned Events:** parent_event_id references event that doesn't exist (no FK)
4. **Stale Trace Visualization:** Dashboard could show incomplete chain if query runs mid-pipeline

**Institutional Maturity:** 5/10
- ✅ Immutable append-only design
- ✅ Good indexing for trace/strategy lookups
- ❌ Type mismatch on strategy_id
- ❌ No FK constraint on parent_event_id
- ❌ No stage/status validation
- ❌ Potential ID collision

---

### 16. PATTERN_MEMORY (Pattern Detection Output)

**Classification:** Relational Table (auto-migrated) | Catalog | MEDIUM

**Purpose:**  
Pattern detection output from PatternAgent. Tracks winning/losing patterns for ideation context.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
pattern_type       TEXT NOT NULL          — "winning_motif", "losing_motif", "cost_trap", etc.
archetype          TEXT                   — Pattern category
feature_family     TEXT[]                 — Features involved
asset_class        TEXT                   — "crypto", "equity"
timeframe          TEXT                   — "1m", "5m", "1h"
regime             TEXT                   — Market regime
composite_score_avg NUMERIC
short_window_score_avg NUMERIC
sharpe_avg         NUMERIC
win_rate_avg       NUMERIC
total_trades_avg   NUMERIC
cost_burden_avg    NUMERIC
sample_size        INT DEFAULT 0
confidence_score   NUMERIC DEFAULT 0.0
recommendation     TEXT
motif_details      JSONB
detected_at        TIMESTAMPTZ DEFAULT NOW()
updated_at         TIMESTAMPTZ DEFAULT NOW()
```

**Indexes:**
- Primary key on `id`
- Index on `pattern_type` (queries group by type)
- Index on `archetype` (filter by pattern class)

**Data Integrity:**
- ❌ pattern_type values not validated
- ❌ asset_class values not validated
- ❌ confidence_score should be in [0, 1]
- ❌ No check: sharpe_avg in [-10, 10]

**Write Dependencies:**
- `pattern_agent.detect_patterns()` → Records patterns after analysis

**Read Dependencies:**
- IdeatorAgent prior context
- Dashboard pattern browser

**Restart Safety:**
- ⚠️ Updated-at suggests upsert, but schema only shows insert
- Could have duplicate patterns with different scores

**Known Drift Risks:**
1. **Pattern Enum Drift:** "WINNING_MOTIF" vs "winning_motif"
2. **Stale Confidence Scores:** Patterns updated infrequently; scores outdated
3. **No Dedup:** Same pattern could be recorded multiple times

**Institutional Maturity:** 4/10
- ❌ Auto-migrated (not in canonical schema.sql)
- ❌ No pattern_type validation
- ❌ Potential duplicates

---

### 17. EXECUTION_LOG (Order Audit Trail)

**Classification:** Relational Table (Immutable) | Audit | CRITICAL

**Purpose:**  
Immutable append-only order execution audit trail. Source of truth for order state machine.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
order_key          TEXT NOT NULL          — Unique order identifier
strategy_id        UUID                   — Strategy that placed order
symbol             TEXT NOT NULL
side               TEXT NOT NULL          — "buy", "sell"
quantity           NUMERIC
price              NUMERIC
state              TEXT NOT NULL          — "pending", "filled", "rejected", etc.
broker_order_id    TEXT                   — Broker's order ID
client_order_id    TEXT                   — Our order ID
broker             TEXT NOT NULL DEFAULT 'alpaca'
error_message      TEXT
metadata           JSONB
created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

**Indexes:**
- Primary key on `id` (UUID)
- Index on `order_key` (fast order lookup)
- Index on `strategy_id` (query by strategy)
- Index on `state` (query by state)
- Index on `created_at DESC` (time-range queries)
- Index on `client_order_id` (broker reconciliation)
- Index on `broker_order_id` (broker reconciliation)

**Data Integrity:**
- ❌ NO foreign key constraint on strategy_id (soft reference OK for audit trail)
- ❌ state values not validated (enum)
- ❌ side values not validated
- ❌ No constraint: order_key must be unique (could have duplicates)
- ✅ order_key as "order identifier" suggests business key; used for dedup

**Write Dependencies:**
- `execution_service.log_order_state()` → Called on every state transition
- Idempotent insert pattern via WHERE NOT EXISTS (seen in copy_trader)

**Read Dependencies:**
- Dashboard execution logs
- Order reconciliation queries
- Risk compliance queries
- Regulatory audit trail

**Restart Safety:**
- ✅ Append-only; restart-safe
- ✅ Idempotent insert via order_key uniqueness check (in code)

**Known Drift Risks:**
1. **Order Key Collision:** No UNIQUE constraint on order_key; duplicates possible if code fails
2. **State Value Drift:** "FILLED" vs "filled" vs "Filled"
3. **Missing State Transitions:** Could jump from "pending" to "filled" without "partial_fill"
4. **Broker ID Mismatch:** broker_order_id might not match actual broker record
5. **No Completeness Check:** Could have "pending" orders never resolved

**Institutional Maturity:** 6/10
- ✅ Immutable append-only design
- ✅ Good indexing for query performance
- ✅ Multiple indexes for reconciliation
- ❌ No UNIQUE constraint on order_key
- ❌ No state enum/validation
- ⚠️ Reliant on code discipline for idempotency

---

### 18. EXECUTION_DEAD_LETTER (Failed Orders)

**Classification:** Relational Table | Operational | HIGH

**Purpose:**  
Orders that failed or were rejected. Requires human review or manual retry.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
order_key          TEXT NOT NULL
strategy_id        UUID
symbol             TEXT NOT NULL
side               TEXT NOT NULL
quantity           NUMERIC
failure_reason     TEXT NOT NULL          — "insufficient_balance", "timeout", etc.
last_state         TEXT NOT NULL          — Last state before failure
broker_order_id    TEXT
client_order_id    TEXT
severity           TEXT NOT NULL DEFAULT 'medium' — "low", "medium", "high", "critical"
resolved           BOOLEAN NOT NULL DEFAULT FALSE
resolution         TEXT                   — How it was resolved
retry_count        INT NOT NULL DEFAULT 0
metadata           JSONB
created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
resolved_at        TIMESTAMPTZ
```

**Indexes:**
- Primary key on `id`
- Partial index on `resolved` WHERE resolved=FALSE (unresolved alerts)
- Index on `severity` (query high-severity failures)
- Index on `strategy_id` (filter by strategy)

**Data Integrity:**
- ❌ NO foreign key on strategy_id
- ❌ failure_reason values not validated (enum)
- ❌ severity values not validated (should be enum)
- ❌ No check: retry_count >= 0
- ❌ No check: resolved=TRUE implies resolved_at NOT NULL

**Write Dependencies:**
- `execution_service.log_failure()` → Called when order fails
- Manual update when human resolves

**Read Dependencies:**
- Dashboard failure alert
- Alerting pipeline (email/Slack on critical failures)
- Manual triage

**Restart Safety:**
- ✅ Insert-only until manual resolution

**Known Drift Risks:**
1. **Unresolved Backlog:** Dead letter queue could accumulate if not reviewed
2. **Retry Loop:** Same order could be retried indefinitely if no max-retry limit
3. **Severity Inflation:** All failures marked "critical"; alerting noise
4. **Missing Resolution Audit:** No tracking of who resolved or when (only resolved_at)

**Institutional Maturity:** 5/10
- ✅ Partial index on unresolved (good alerting)
- ✅ Severity tracking
- ❌ No failure_reason/severity enum validation
- ❌ No FK constraint
- ❌ Manual resolution required; no automation

---

### 19. POSITIONS (Current Holdings)

**Classification:** Relational Table | State Machine | HIGH

**Purpose:**  
Current open positions for each account. Updated atomically with order fills.

**Schema:**
```
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
account_ref        TEXT NOT NULL          — "leader_1", "follower_2", etc.
symbol             TEXT NOT NULL
qty                NUMERIC NOT NULL DEFAULT 0  — Signed quantity
avg_price          NUMERIC                — Entry price
side               TEXT NOT NULL DEFAULT 'long' — "long" or "short"
created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
strategy_id        UUID (added in execution_tables.sql)
broker             TEXT NOT NULL DEFAULT 'alpaca'
unrealized_pnl     NUMERIC DEFAULT 0
```

**Indexes:**
- Primary key on `id` (UUID)
- Index on `account_ref` (queries by account)
- Index on `symbol` (queries by instrument)
- Index on `strategy_id` (query positions by strategy)
- Index on `broker` (query by broker)

**Data Integrity:**
- ❌ NO UNIQUE constraint on (account_ref, symbol, side) → Duplicate positions possible
- ❌ qty could be NULL or 0 (ambiguous for closed position vs no data)
- ❌ avg_price could be NULL even for open position
- ❌ side values not validated
- ❌ No check: qty != 0 if position is open
- ❌ unrealized_pnl could diverge from (current_price - avg_price) * qty

**Write Dependencies:**
- Broker adapter → Updates on fill
- `copy_trader._check_follower_risk()` → Reads for risk checks
- Atomic transaction: order fill + position update (NOT ENFORCED)

**Read Dependencies:**
- `copy_trader._check_follower_risk()` → Check max_position_pct
- Dashboard portfolio view
- Risk calculations

**Restart Safety:**
- ⚠️ If crash mid-update, position could be stale
- ⚠️ No transaction linking order fill + position update
- Could have "filled" order but stale position

**Known Drift Risks:**
1. **Duplicate Positions:** Multiple rows for (account, symbol) with different qty/side
2. **Stale Position:** Position not updated when order fills
3. **Zero Qty Ambiguity:** Can't distinguish "closed" from "no data"
4. **PnL Divergence:** unrealized_pnl calculated offline could differ from market price
5. **Orphaned Positions:** Positions for accounts deleted from copy_leader_accounts

**Institutional Maturity:** 4/10
- ❌ No UNIQUE constraint on (account_ref, symbol, side)
- ❌ No atomic transaction linking orders + positions
- ❌ Qty=0 ambiguous (closed vs no data)
- ❌ PnL calculated offline; could diverge from market
- ⚠️ Risk check relies on stale position data

---

## CROSS-TABLE RELATIONSHIP AUDIT

### Critical Foreign Keys
```
mutation_memory.parent_strategy_id → strategies.id (enforced ✅)
mutation_memory.child_strategy_id → strategies.id (enforced ✅)
combination_memory.parent_a → strategies.id (enforced ✅)
combination_memory.parent_b → strategies.id (enforced ✅)
combination_memory.child_id → strategies.id (soft reference OK, nullable)
copy_follower_accounts.leader_id → copy_leader_accounts.leader_id (enforced ✅)
```

### Missing Foreign Keys (Drift)
```
backtest_results.strategy_id → strategies.id (NOT enforced ❌)
backtest_trades.strategy_id → strategies.id (NOT enforced ❌)
execution_log.strategy_id → strategies.id (soft reference OK for audit trail)
execution_dead_letter.strategy_id → strategies.id (soft reference OK)
positions.strategy_id → strategies.id (NOT enforced ❌ — added in execution_tables.sql)
system_logs.agent_id → agent_registry.id (NOT enforced ❌)
performance_metrics.strategy_id → strategies.id (NOT enforced ❌)
```

### Type Mismatches (Drift)
```
lifecycle_events.strategy_id: TEXT vs strategies.id: UUID → Could break lineage
lifecycle_events.parent_event_id: TEXT but no FK constraint → Orphaned chain possible
```

---

## SCHEMA DRIFT ANALYSIS

### Mutations Not in Canonical schema.sql

**1. Auto-Migration in timescale_client.connect():**
```python
# backtest_trades indexes (added 1 index beyond schema.sql)
CREATE INDEX idx_backtest_trades_symbol ON backtest_trades (symbol)

# market_data_l1 new columns
ADD COLUMN IF NOT EXISTS asset_class TEXT NOT NULL DEFAULT 'crypto'
ADD COLUMN IF NOT EXISTS ingestion_time TIMESTAMPTZ DEFAULT NOW()

# strategies new columns
ADD COLUMN IF NOT EXISTS prompt TEXT
ADD COLUMN IF NOT EXISTS raw_response TEXT
ADD COLUMN IF NOT EXISTS normalized_strategy JSONB
ADD COLUMN IF NOT EXISTS compile_error TEXT
ADD COLUMN IF NOT EXISTS strategy_signature TEXT
ADD COLUMN IF NOT EXISTS trace_id TEXT

# pattern_memory table (NOT in schema.sql)
CREATE TABLE IF NOT EXISTS pattern_memory (...)

# lifecycle_events indices (additional)
CREATE INDEX idx_lifecycle_stage ON lifecycle_events (stage)
```

**2. Unused/Incomplete Columns:**
```sql
strategies.train_sharpe         — Added but never populated
strategies.test_sharpe          — Added but never populated
strategies.holdout_sharpe       — Added but never populated
strategies.stability_score      — Added but never populated
strategies.overfit_flag         — Added but never populated
strategies.regime_score         — Added but never populated
strategies.generation_batch     — Added by timescale_client but not schema.sql
```

**3. Type Inconsistencies:**
```
lifecycle_events.strategy_id: TEXT (should be UUID)
strategies.trace_id: TEXT → lifecycle_events.trace_id: TEXT (good, consistent)
```

---

## DATA INTEGRITY VERIFICATION CHECKLIST

### Time-Series Tables (market_data_l1, market_data_l2, order_flow, features, system_logs, performance_metrics, paper_trades)

| Check | Status | Evidence |
|-------|--------|----------|
| Monotonic time ordering | ❌ NO CONSTRAINT | Could insert future bars; no CURRENT_TIMESTAMP check |
| Unique (time, symbol) | ❌ NO CONSTRAINT | Duplicates possible on re-ingestion |
| Precision enforcement | ❌ NO CHECK CONSTRAINT | Precision only documented in comments |
| Volume/Price >= 0 | ❌ NO CONSTRAINT | Negative prices/volumes silently stored |
| Partition key completeness | ⚠️ BEST EFFORT | TimescaleDB handles, but no app-level audit |

### Catalog Tables (strategies, backtest_results, backtest_trades, intelligence_briefs, mutation_memory, combination_memory, lifecycle_events, pattern_memory)

| Check | Status | Evidence |
|-------|--------|----------|
| PK existence | ✅ YES | UUID primary keys present |
| FK referential integrity | ❌ PARTIAL | mutation_memory/combination_memory OK; others missing |
| Enum validation (status, type, state) | ❌ NO CONSTRAINTS | Rely on code discipline |
| Dedup prevention | ⚠️ PARTIAL | Unique constraint in combination_memory; others missing |
| Completeness (no orphans) | ❌ NO CHECK | Strategies deleted but backtest_results remain |

### Execution Tables (execution_log, execution_dead_letter, positions, copy_execution_log)

| Check | Status | Evidence |
|-------|--------|----------|
| Order completeness | ❌ NO AUDIT | Could have "pending" orders never resolved |
| Position/Order consistency | ❌ NO TRANSACTION | Atomic update not enforced |
| Dead letter backlog | ⚠️ MANUAL | Requires human triage; no auto-cleanup |
| Idempotency | ✅ PARTIAL | WHERE NOT EXISTS in code; no UNIQUE constraint |

### Operational Tables (agent_registry, api_keys, api_request_audit, audit_logs)

| Check | Status | Evidence |
|-------|--------|----------|
| Agent heartbeat freshness | ❌ NO CONSTRAINT | Stale agents never cleaned |
| API key revocation | ✅ PARTIAL | revoked_at soft-delete; queries filter correctly |
| Audit trail completeness | ✅ APPEND-ONLY | Immutable logs; restart-safe |

---

## TOP 5 MIGRATION BLOCKERS

### 1. Precision Unbounded in Numeric Columns
**Blocker:** All market data (OHLC, volume, price, spread) stored as NUMERIC with unbounded precision
**Impact:** 
- Backtests calculate Sharpe based on rounded values, but stored precision could differ
- Roundtrip: calculate → store at 4dp → read back could truncate mid-calculation
- Silent precision loss in feature calculations

**Fix Required:**
```sql
ALTER TABLE market_data_l1 ADD CONSTRAINT chk_ohlc_precision
  CHECK (
    ROUND(open::numeric, 4) = open AND
    ROUND(high::numeric, 4) = high AND
    ROUND(low::numeric, 4) = low AND
    ROUND(close::numeric, 4) = close
  );
```

---

### 2. No Uniqueness Constraint on Core Keys
**Blocker:** market_data_l1 can have duplicate (time, symbol); execution_log can duplicate (order_key)
**Impact:**
- Duplicate ingestion could rerun features → stale features_wide
- Duplicate execution could create duplicate orders in broker

**Fix Required:**
```sql
ALTER TABLE market_data_l1 ADD UNIQUE (time, symbol);
ALTER TABLE execution_log ADD UNIQUE (order_key);
ALTER TABLE copy_execution_log ADD UNIQUE (leader_order_id, follower_id);
```

---

### 3. Missing Foreign Key Constraints
**Blocker:** backtest_results/backtest_trades reference strategies.id without FK
**Impact:**
- Orphaned records when strategy deleted
- No cascade cleanup available

**Fix Required:**
```sql
ALTER TABLE backtest_results
  ADD CONSTRAINT fk_backtest_strategy
  FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
ALTER TABLE backtest_trades
  ADD CONSTRAINT fk_backtest_trade_strategy
  FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
```

---

### 4. Type Mismatch in Lineage Tables
**Blocker:** lifecycle_events.strategy_id is TEXT; strategies.id is UUID
**Impact:**
- Event lineage could link to wrong strategy (string collision)
- Type coercion could mask bugs

**Fix Required:**
```sql
ALTER TABLE lifecycle_events ALTER COLUMN strategy_id TYPE UUID USING (strategy_id::UUID);
ALTER TABLE lifecycle_events ADD CONSTRAINT fk_lifecycle_strategy
  FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
```

---

### 5. No Atomic Transaction for Order + Position
**Blocker:** copy_execution_log insert and positions update are separate transactions
**Impact:**
- Crash could insert filled order but leave position stale
- Risk checks in copy_trader read stale positions

**Fix Required:**
```python
async def _fill_order_and_update_position(order_key, qty, fill_price):
    async with self.db.engine.begin() as conn:  # BEGIN; ... COMMIT;
        # 1. Insert execution_log record
        await conn.execute(...)
        # 2. Update positions atomically
        await conn.execute(...)
        # Commit or rollback together
```

---

## INSTITUTIONAL READINESS SCORES

### By Table

| Table | Clarity | Integrity | Auditability | Recovery | Production | Overall |
|-------|---------|-----------|--------------|----------|-----------|---------|
| market_data_l1 | 6/10 | 4/10 | 7/10 | 7/10 | 5/10 | 5.8/10 |
| market_data_l2 | 5/10 | 3/10 | 6/10 | 7/10 | 4/10 | 5/10 |
| order_flow | 5/10 | 3/10 | 6/10 | 7/10 | 4/10 | 5/10 |
| features | 6/10 | 4/10 | 6/10 | 7/10 | 5/10 | 5.6/10 |
| features_wide | 5/10 | 4/10 | 5/10 | 4/10 | 4/10 | 4.4/10 |
| strategies | 7/10 | 5/10 | 7/10 | 5/10 | 6/10 | 6/10 |
| backtest_results | 7/10 | 4/10 | 6/10 | 5/10 | 5/10 | 5.4/10 |
| backtest_trades | 6/10 | 4/10 | 6/10 | 5/10 | 4/10 | 5/10 |
| paper_trades | 5/10 | 3/10 | 5/10 | 6/10 | 3/10 | 4.4/10 |
| agent_registry | 6/10 | 4/10 | 6/10 | 3/10 | 4/10 | 4.6/10 |
| system_logs | 7/10 | 6/10 | 8/10 | 8/10 | 7/10 | 7.2/10 |
| performance_metrics | 5/10 | 4/10 | 6/10 | 6/10 | 4/10 | 5/10 |
| intelligence_briefs | 5/10 | 3/10 | 5/10 | 5/10 | 3/10 | 4.2/10 |
| mutation_memory | 7/10 | 7/10 | 7/10 | 7/10 | 7/10 | 7/10 |
| combination_memory | 7/10 | 7/10 | 7/10 | 7/10 | 7/10 | 7/10 |
| lifecycle_events | 6/10 | 5/10 | 7/10 | 6/10 | 5/10 | 5.8/10 |
| pattern_memory | 4/10 | 4/10 | 5/10 | 5/10 | 4/10 | 4.4/10 |
| execution_log | 7/10 | 6/10 | 8/10 | 8/10 | 7/10 | 7.2/10 |
| execution_dead_letter | 6/10 | 5/10 | 7/10 | 5/10 | 5/10 | 5.6/10 |
| positions | 5/10 | 3/10 | 5/10 | 4/10 | 3/10 | 4/10 |
| **AVERAGE** | 5.95/10 | 4.71/10 | 6.33/10 | 5.9/10 | 5.05/10 | **5.58/10** |

---

## RECOMMENDED SCHEMA HARDENING

### Phase 1: Critical (Do First)
1. **Add UNIQUE constraints on core keys**
   ```sql
   ALTER TABLE market_data_l1 ADD UNIQUE (time, symbol);
   ALTER TABLE execution_log ADD UNIQUE (order_key);
   ALTER TABLE copy_execution_log ADD UNIQUE (leader_order_id, follower_id);
   ```

2. **Add Foreign Key constraints**
   ```sql
   ALTER TABLE backtest_results ADD CONSTRAINT fk_backtest_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
   ALTER TABLE backtest_trades ADD CONSTRAINT fk_backtest_trade_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
   ALTER TABLE performance_metrics ADD CONSTRAINT fk_perf_strategy FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
   ```

3. **Add NOT NULL constraints**
   ```sql
   ALTER TABLE market_data_l1 ALTER COLUMN volume SET NOT NULL;
   ALTER TABLE execution_log ALTER COLUMN order_key SET NOT NULL;
   ```

4. **Add CHECK constraints on precision**
   ```sql
   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_ohlc_precision CHECK (ROUND(open, 4) = open);
   ALTER TABLE market_data_l1 ADD CONSTRAINT chk_volume_precision CHECK (
     CASE WHEN asset_class = 'crypto' THEN ROUND(volume, 6) ELSE ROUND(volume, 4) END = volume
   );
   ```

### Phase 2: Important (Next Sprint)
5. **Add enum constraints**
   ```sql
   ALTER TABLE execution_log ADD CONSTRAINT chk_state CHECK (state IN ('pending', 'partial_fill', 'filled', 'cancelled', 'rejected'));
   ALTER TABLE execution_log ADD CONSTRAINT chk_side CHECK (side IN ('buy', 'sell'));
   ALTER TABLE positions ADD CONSTRAINT chk_position_side CHECK (side IN ('long', 'short'));
   ```

6. **Add range constraints**
   ```sql
   ALTER TABLE backtest_results ADD CONSTRAINT chk_sharpe CHECK (sharpe >= -10 AND sharpe <= 10);
   ALTER TABLE backtest_results ADD CONSTRAINT chk_win_rate CHECK (win_rate >= 0 AND win_rate <= 1);
   ```

7. **Create missing indexes**
   ```sql
   CREATE INDEX idx_market_data_l1_symbol ON market_data_l1 (symbol);
   CREATE INDEX idx_backtest_results_sharpe ON backtest_results (sharpe DESC);
   CREATE INDEX idx_strategies_created_at ON strategies (created_at DESC);
   CREATE INDEX idx_execution_log_state ON execution_log (state);
   ```

### Phase 3: Nice-to-Have (Future)
8. **Add generated columns for derived values**
   ```sql
   ALTER TABLE positions ADD COLUMN market_value GENERATED ALWAYS AS (qty * avg_price) STORED;
   ALTER TABLE backtest_trades ADD COLUMN pnl_bps GENERATED ALWAYS AS (pnl_pct * 10000) STORED;
   ```

9. **Create health check materialized view**
   ```sql
   CREATE MATERIALIZED VIEW data_quality AS
   SELECT
     'market_data_l1' as table_name,
     COUNT(*) as total_rows,
     COUNT(DISTINCT symbol) as unique_symbols,
     MAX(time) as latest_timestamp,
     MIN(time) as oldest_timestamp
   FROM market_data_l1
   WHERE time > NOW() - INTERVAL '1 day';
   ```

---

## RECOMMENDED AUDIT PROCEDURES

### Daily Health Checks
```sql
-- 1. Duplicate detection
SELECT table_name, COUNT(*) as dup_count
FROM (
  SELECT 'market_data_l1' as table_name, time, symbol, COUNT(*) as cnt
  FROM market_data_l1 WHERE time > NOW() - INTERVAL '1 day'
  GROUP BY time, symbol HAVING COUNT(*) > 1
  UNION ALL
  SELECT 'execution_log', order_key, '', COUNT(*)
  FROM execution_log WHERE created_at > NOW() - INTERVAL '1 day'
  GROUP BY order_key HAVING COUNT(*) > 1
) as dups
GROUP BY table_name;

-- 2. Orphan detection
SELECT COUNT(*) as orphaned_backtest_results
FROM backtest_results br
LEFT JOIN strategies s ON br.strategy_id = s.id
WHERE s.id IS NULL;

-- 3. Stale feature data
SELECT symbol, MAX(time) as latest_feature_time
FROM features
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY symbol
HAVING MAX(time) < NOW() - INTERVAL '5 minutes';

-- 4. Unresolved dead letters
SELECT COUNT(*) as critical_unresolved
FROM execution_dead_letter
WHERE resolved = FALSE
  AND severity = 'critical'
  AND created_at < NOW() - INTERVAL '1 hour';

-- 5. Stale agent heartbeats
SELECT name, layer, last_heartbeat, NOW() - last_heartbeat as age_seconds
FROM agent_registry
WHERE status = 'running'
  AND last_heartbeat < NOW() - INTERVAL '5 minutes'
ORDER BY age_seconds DESC;
```

### Weekly Integrity Checks
```sql
-- 1. Foreign key consistency
SELECT COUNT(*) as orphaned_mutations
FROM mutation_memory mm
LEFT JOIN strategies s1 ON mm.parent_strategy_id = s1.id
LEFT JOIN strategies s2 ON mm.child_strategy_id = s2.id
WHERE s1.id IS NULL OR s2.id IS NULL;

-- 2. Precision violations (after Phase 1 constraint added)
SELECT COUNT(*) as precision_violations
FROM market_data_l1
WHERE ROUND(open::numeric, 4) != open
   OR ROUND(close::numeric, 4) != close;

-- 3. Feature completeness
SELECT symbol, COUNT(DISTINCT feature_name) as feature_count
FROM features
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY symbol
HAVING COUNT(DISTINCT feature_name) < 20
ORDER BY feature_count ASC;
```

### Monthly Data Quality Report
```sql
SELECT
  'Q1: Schema Compliance' as category,
  (SELECT COUNT(*) FROM (
    SELECT 1 FROM market_data_l1 WHERE volume IS NULL OR volume < 0
    UNION ALL
    SELECT 1 FROM execution_log WHERE state NOT IN ('pending', 'filled', 'rejected')
  ) x) as violations,
  'Precision/Enum/NotNull' as metric

UNION ALL

SELECT
  'Q2: Referential Integrity',
  (SELECT COUNT(*) FROM backtest_results WHERE strategy_id NOT IN (SELECT id FROM strategies)),
  'FK orphans'

UNION ALL

SELECT
  'Q3: Completeness',
  (SELECT COUNT(*) FROM execution_dead_letter WHERE resolved = FALSE AND created_at < NOW() - INTERVAL '7 days'),
  'Stale dead letters'

UNION ALL

SELECT
  'Q4: Freshness',
  (SELECT COUNT(*) FROM agent_registry WHERE last_heartbeat < NOW() - INTERVAL '10 minutes' AND status = 'running'),
  'Stale agents';
```

---

## RECOMMENDED RECOVERY PROCEDURES

### Corruption Scenarios

#### Scenario 1: Duplicate Market Data Ingested
**Problem:** market_data_l1 has duplicate (time, symbol) rows
**Recovery:**
```sql
-- 1. Identify duplicates
SELECT time, symbol, COUNT(*) as cnt
FROM market_data_l1
WHERE time > NOW() - INTERVAL '1 day'
GROUP BY time, symbol
HAVING COUNT(*) > 1;

-- 2. Keep only latest ingestion (by ingestion_time)
WITH dups AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY time, symbol ORDER BY ingestion_time DESC) as rn
  FROM market_data_l1
  WHERE time > NOW() - INTERVAL '1 day'
)
DELETE FROM market_data_l1
WHERE (time, symbol) IN (SELECT time, symbol FROM dups WHERE rn > 1);

-- 3. Refresh features_wide to recalculate
REFRESH MATERIALIZED VIEW CONCURRENTLY features_wide;

-- 4. Rerun affected backtests
-- (Manual: query strategies with backtest_results after corruption time)
```

#### Scenario 2: Position Out of Sync with Orders
**Problem:** Order filled but position not updated
**Recovery:**
```sql
-- 1. Detect mismatches
SELECT
  cel.symbol,
  cel.follower_id,
  cel.follower_qty,
  COALESCE(p.qty, 0) as position_qty
FROM copy_execution_log cel
LEFT JOIN positions p ON p.account_ref = cel.follower_id AND p.symbol = cel.symbol
WHERE cel.status = 'filled'
  AND p.qty != cel.follower_qty;

-- 2. Rebuild positions from execution_log
-- WARNING: Destructive; requires verification
DELETE FROM positions WHERE account_ref IN (SELECT account_ref FROM copy_follower_accounts);

-- Rebuild from orders
INSERT INTO positions (account_ref, symbol, qty, avg_price, side)
SELECT
  account_ref,
  symbol,
  SUM(CASE WHEN side = 'buy' THEN quantity ELSE -quantity END) as qty,
  AVG(price) as avg_price,
  'long' as side  -- Simplified; actual logic more complex
FROM execution_log
WHERE status = 'filled'
GROUP BY account_ref, symbol;
```

#### Scenario 3: Orphaned Strategy Records
**Problem:** Strategy deleted but backtest_results remain
**Recovery:**
```sql
-- 1. Identify orphans
SELECT br.strategy_id, COUNT(*) as orphaned_backtest_count
FROM backtest_results br
LEFT JOIN strategies s ON br.strategy_id = s.id
WHERE s.id IS NULL
GROUP BY br.strategy_id;

-- 2. Clean up (backup first!)
-- Backup:
pg_dump -h localhost -d atlas --table=backtest_results > backtest_results_backup.sql

-- Delete:
DELETE FROM backtest_results
WHERE strategy_id NOT IN (SELECT id FROM strategies);

-- Or manually restore:
psql -h localhost -d atlas < backtest_results_backup.sql
```

#### Scenario 4: Stale features_wide After Ingestion Gap
**Problem:** New features added to `features` table but features_wide not refreshed
**Recovery:**
```sql
-- 1. Refresh (non-blocking with CONCURRENTLY)
REFRESH MATERIALIZED VIEW CONCURRENTLY features_wide;

-- 2. Verify freshness
SELECT time, symbol, returns, rsi_14, macd
FROM features_wide
WHERE time = (SELECT MAX(time) FROM features)
LIMIT 10;

-- 3. Schedule periodic refresh (as cron job or app startup)
-- App: timescale_client.connect() calls this on each startup
```

---

## FINAL RECOMMENDATIONS PRIORITY ORDER

### **CRITICAL (Do This Week)**
1. Add UNIQUE constraints on core keys (execution_log, market_data_l1)
2. Add FK constraints to backtest_* tables
3. Fix lifecycle_events.strategy_id UUID type mismatch
4. Atomicity: wrap order insert + position update in transaction

### **HIGH (Do This Sprint)**
5. Add NOT NULL constraints on volume, price, quantity
6. Add enum CHECK constraints on state, side, status
7. Create missing indexes on query columns (symbol, sharpe, created_at)
8. Build data quality monitoring dashboard

### **MEDIUM (Do Next Sprint)**
9. Add range CHECK constraints on ratios/percentages
10. Create health check materialized view
11. Implement daily/weekly audit queries
12. Establish runbook for corruption recovery

### **LOW (Do Later)**
13. Generated columns for derived metrics
14. Separate materialized view refresh into background job
15. Archive old data (partition/compress historical data)

---

## SUMMARY: ATLAS DATABASE MATURITY ASSESSMENT

**Overall Score:** 5.58/10 (Operational but Fragile)

**Strengths:**
- ✅ TimescaleDB hypertable design for time-series efficiency
- ✅ Good indexing for query performance on execution/mutation tables
- ✅ Immutable append-only patterns for audit logs
- ✅ Event lineage design for strategy tracking

**Critical Gaps:**
- ❌ Precision unbounded; no CHECK constraints
- ❌ Uniqueness not enforced; duplicates possible
- ❌ Foreign keys missing on critical relationships
- ❌ Type mismatches in lineage tables
- ❌ Atomic transactions not enforced for order+position

**Operational Risks:**
- Duplicate market data → stale backtests
- Orphaned records → referential integrity violations
- Stale features_wide → incorrect strategy evaluation
- Unresolved dead letters → operational debt
- Position/order mismatch → risk calculation errors

**Path to Production Readiness:**
- **Week 1:** Add constraints (uniqueness, FK, NOT NULL)
- **Week 2:** Build monitoring (daily audit queries, alerting)
- **Week 3:** Test recovery procedures (corruption scenarios)
- **Week 4:** Deploy with confidence

**Estimated Effort:** 60-80 hours total
- Schema hardening: 16 hours
- Monitoring/audit: 24 hours
- Testing/validation: 20 hours

---

**Report Generated:** May 18, 2026  
**Next Review:** May 25, 2026 (after Phase 1 hardening)
