# PHASE 24 — Failure Ledger

**Soak Run:** 2026-05-20 (86 minutes)  
**Total Failures Documented:** 8  

---

## F-001: Schema Drift — UndefinedColumn Errors

| Field | Value |
|---|---|
| **Subsystem** | L1–L7 (cross-cutting) |
| **Root Cause** | Database schema is missing columns that the code expects. Multiple `ALTER TABLE ADD COLUMN IF NOT EXISTS` migrations are missing from `timescale_client.py` or were never executed. |
| **Severity** | **P0 — Critical** |
| **Count** | 104 |
| **Replay Implications** | High — no event_store, no audit_ledger, no trace_graph means replay is impossible |
| **Governance Implications** | High — governance events missing columns, audit trail empty |
| **Affected Columns** | `event_store.sequence`, `paper_trades.id`, `paper_trades.qty`, `correlation_memory.correlation_value`, `strategies.mutation_type`, `external_scout_memory.details`, `lifecycle_events.agent_name` |
| **Exact Fix** | Add migration commands to `timescale_client.py` to create all missing columns |
| **Validation After Fix** | Re-run soak and verify 0 UndefinedColumn errors |

---

## F-002: Data Type Errors (String vs Datetime)

| Field | Value |
|---|---|
| **Subsystem** | L1 Scout Network (RegimeScout, LiquidityScout, ExecutionRealismEngine) |
| **Root Cause** | Scout engines pass Python string representations of timestamps (e.g., `'2026-05-20T14:10:30.630270+00:00'`) instead of proper `datetime.datetime` objects to PostgreSQL queries. |
| **Severity** | **P0 — Critical** |
| **Count** | 543 |
| **Replay Implications** | Medium — scout data not persisted, affecting historical replay context |
| **Governance Implications** | Low — doesn't bypass governance, but blocks scout analysis |
| **Affected Symbols** | BTCUSDT, ETHUSDT, SOLUSDT, SPY, QQQ, AAPL, MSFT, NVDA (344 scout errors + 199 execution realism errors) |
| **Exact Fix** | Convert timestamp strings to `datetime` objects using `datetime.fromisoformat()` before passing to asyncpg queries in regime_scout.py, liquidity_scout.py, and execution_realism_engine.py |
| **Validation After Fix** | Verify all 8 symbols pass analysis without DataError |

---

## F-003: Unbounded Agent Restart Loop

| Field | Value |
|---|---|
| **Subsystem** | L2 Strategy Evolution, Scout Network |
| **Root Cause** | `IdeatorV2_0_R` and `SourceReliabilityEngine` complete their natural lifecycle early (tasks exit quickly), triggering `_run_with_retry` → `start()` restart loop at ~5s intervals. |
| **Severity** | **P1 — High** |
| **Count** | 1,994 restart events |
| **Replay Implications** | Medium — generates excessive lifecycle_events, creates noise in replay |
| **Governance Implications** | Low — governance not bypassed, but inefficient |
| **Exact Fix** | Option A: Add `asyncio.sleep()` in the agent's `run()` to match its configured interval. Option B: Modify `_run_with_retry` to check if task was "completed successfully" vs "failed" and only restart on failure. Option C: Both. |
| **Validation After Fix** | Verify agent starts exactly once and re-starts only on failure |

---

## F-004: SourceReliabilityEngine — NameError

| Field | Value |
|---|---|
| **Subsystem** | Scout Network |
| **Root Cause** | `source_reliability_engine.py` uses `asyncio.sleep()` without importing `asyncio` at module level or the method has `asyncio` shadowed by a parameter/variable. |
| **Severity** | **P2 — Medium** |
| **Count** | ~5 |
| **Replay Implications** | Low |
| **Governance Implications** | Low |
| **Exact Fix** | Add `import asyncio` at top of file or fix variable shadowing |
| **Validation After Fix** | Verify engine starts without NameError |

---

## F-005: NewsIntelligenceEngine — DNS Failure

| Field | Value |
|---|---|
| **Subsystem** | Scout Network (News Intelligence) |
| **Root Cause** | External RSS feed URLs return DNS resolution failures. The engine's `aiohttp` requests fail on `getaddrinfo`. |
| **Severity** | **P2 — Medium** |
| **Count** | ~5 |
| **Replay Implications** | Low — external dependency, doesn't affect internal replay |
| **Governance Implications** | None |
| **Exact Fix** | Add retry logic with exponential backoff and logging improvements. Consider caching last successful feed content. |
| **Validation After Fix** | Verify engine degrades gracefully without crashing |

---

## F-006: Claude API HTTP 400 Errors

| Field | Value |
|---|---|
| **Subsystem** | L7 Meta Intelligence (ClaudeClient) |
| **Root Cause** | Claude API returning HTTP 400 (bad request), likely from malformed prompts or rate limiting. |
| **Severity** | **P3 — Low** |
| **Count** | ~30 |
| **Replay Implications** | None |
| **Governance Implications** | None |
| **Exact Fix** | Improve error handling in ClaudeClient to differentiate between recoverable (429, 503) and non-recoverable (400) errors |
| **Validation After Fix** | Verify ClaudeClient handles 400 without crashing the calling agent |

---

## F-007: FeatureEvolutionEngine — SQL Syntax Error

| Field | Value |
|---|---|
| **Subsystem** | L7 Meta Intelligence |
| **Root Cause** | Malformed SQL query with a syntax error near `:` (likely an unescaped parameter or f-string formatting issue). |
| **Severity** | **P2 — Medium** |
| **Count** | ~5 |
| **Replay Implications** | Low |
| **Governance Implications** | None |
| **Exact Fix** | Fix SQL query syntax, ensure proper parameterization |
| **Validation After Fix** | Verify FeatureEvolutionEngine SQL executes without syntax error |

---

## F-008: Empty Core Tables (event_store, audit_ledger, etc.)

| Field | Value |
|---|---|
| **Subsystem** | L7 Meta Intelligence, Governance |
| **Root Cause** | Multiple core tables (event_store, audit_ledger, drift_detection, system_health, source_performance_log) remained empty despite 86 minutes of runtime. Likely due to the row-level INSERTs failing silently or the dependent agents crashing before writing. |
| **Severity** | **P1 — High** |
| **Count** | 6 tables empty |
| **Replay Implications** | **Critical** — no event_store = no replay capability |
| **Governance Implications** | **Critical** — no audit_ledger = no governance audit trail |
| **Exact Fix** | Investigate each empty table: (1) Check if INSERT statements fail due to schema drift, (2) Add logging for write failures, (3) Fix schema drift first |
| **Validation After Fix** | Re-run and verify event_store and audit_ledger have entries after 30 minutes |

---

## Summary

| Priority | Count | Fix Complexity |
|---|---|---|
| **P0 — Critical** | 2 (F-001, F-002) | Medium — adding columns + datetime fixes |
| **P1 — High** | 2 (F-003, F-008) | Low-Medium — restart logic + investigation |
| **P2 — Medium** | 3 (F-004, F-005, F-007) | Low |
| **P3 — Low** | 1 (F-006) | Low |
