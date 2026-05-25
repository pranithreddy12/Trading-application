# Phase 25 — Scout Economic Activation: Readiness Assessment

**Date:** 2026-05-22  
**Status:** SUBMITTED FOR REVIEW  
**Prepared by:** Buffy (ATLAS Orchestrator)

---

## Decision Record

| Status | |
|--------|---|
| **Submission** | ☑️ SUBMITTED for review |
| **Approval** | ☐ PENDING — awaiting user decision |
| **Code changes** | ☐ NOT YET EXECUTED — this is an analysis-only submission |

## Executive Summary

Phase 25 aims to transform the scout network from structurally operational into economically influential. This document presents a comprehensive analysis of the current state, three independent root causes for the scout pipeline failure, and a detailed execution plan for the 8 sub-phases of Phase 25.

**Key Verdict: The system is ready for Phase 25 execution, but NO structural code changes have been made yet.** The analysis below identifies exactly what needs to change and why.

**Scope note:** This readiness assessment covers all 10 scouts. Internal scouts (Regime, Liquidity, Correlation) are confirmed active. External scouts (Reddit, News, YouTube, Discord, Podcast, Competition) are DNS-blocked in this local dev environment — this is an **environment-specific** limitation, not an architectural flaw. Production environments with working DNS would resolve this automatically.

---

## 1. Current State — Scout Network Inventory

### 1.1 Scout Agents

| # | Scout | Type | Layer | Status | Writes To |
|---|-------|------|-------|--------|-----------|
| 1 | **RegimeScout** | Internal | L1 | ✅ **Active** — 1,376 rows | `market_regime_memory` |
| 2 | **LiquidityScout** | Internal | L1 | ✅ **Active** — 712 rows | `liquidity_intelligence` |
| 3 | **CorrelationScout** | Internal | L1 | ✅ **Active** — 38 rows | `correlation_memory` |
| 4 | **ExecutionScout** | Internal | L5 | ⚠️ Idle — 0 rows (no trade data) | `execution_intelligence` |
| 5 | **RedditScout** | External | L7 | ❌ DNS blocked | `external_scout_memory` |
| 6 | **NewsIntelligenceEngine** | External | Scout | ❌ DNS blocked | `external_scout_memory` |
| 7 | **YouTubeScout** | External | L7 | ❌ DNS blocked | `external_scout_memory` |
| 8 | **DiscordScout** | External | L7 | ❌ DNS blocked | `external_scout_memory` |
| 9 | **PodcastScout** | External | L7 | ❌ DNS blocked | `external_scout_memory` |
| 10 | **CompetitionScout** | External | L7 | ❌ DNS blocked | `external_scout_memory` |

### 1.2 Scout Infrastructure Tables

| Table | Rows | Purpose |
|-------|:----:|---------|
| `market_regime_memory` | **1,376** | ✅ Internal regime intelligence |
| `liquidity_intelligence` | **712** | ✅ Internal liquidity intelligence |
| `correlation_memory` | **38** | ✅ Internal correlation intelligence |
| `execution_intelligence` | **0** | ⚠️ Waiting for execution data |
| `scout_signals` | **0** | ❌ **CRITICAL: Nothing writes here** |
| `external_scout_memory` | **0** | ❌ DNS blocked |
| `scout_quarantine` | **0** | ✅ Empty (no validation failures) |
| `scout_poison_quarantine` | **0** | ❌ Anti-poisoning engine is deaf |
| `scout_signal_attribution` | **0** | ❌ Not populated |
| `scout_synthesis_log` | **0** | ❌ Not populated |
| `source_performance_log` | **0** | ❌ Not populated |
| `failed_inserts` | **53** | ⚠️ Pre-existing (non-scout) |

### 1.3 Internal Scout — Data Freshness

| Scout | Last Data Point | Status |
|-------|:---------------:|:------:|
| RegimeScout | 2026-05-22 08:39 UTC | ✅ **Active — updating every 60s** |
| LiquidityScout | 2026-05-22 08:38 UTC | ✅ **Active — updating every 120s** |
| CorrelationScout | 2026-05-22 08:35 UTC | ✅ **Active — updating every 300s** |
| ExecutionScout | None | ⚠️ Idle — no trades to analyze |

### 1.4 Latest Scout Values

**Regime (latest):**
- NVDA: `high_vol` / `mean_reverting` (conf=1.00)
- BTCUSDT: `high_vol` / `choppy` (conf=1.00)
- ETHUSDT: `high_vol` / `choppy` (conf=1.00)
- SPY: `normal_vol` / `choppy` (conf=1.00)
- Overall: 516 `high_vol` entries, 860 `normal_vol` entries

**Liquidity (latest):**
- ETHUSDT: 80/100 — `excellent`
- NVDA/AAPL: 76/100 — `stable`
- SPY/MSFT/BTCUSDT: 0/100 — `dangerous` (volume heuristic, no L2 data)
- Overall: Mixed — some symbols showing dangerous liquidity

**Correlation (latest):**
- Avg pairwise: 0.24 — `diversified`
- Cluster: `tech_heavy`
- Risk: `diversified` — No spikes detected

---

## 2. Root Cause Analysis: Why `scout_signals = 0`

### Root Cause #1 — No Code Writes to `scout_signals` TABLE

**The `scout_signals` table exists but NO agent code inserts into it.**

Every scout writes to its own specialized table, but none write to the unified `scout_signals` table that the AntiPoisoningEngine and other consumers query.

**Evidence:**
- `RegimeScout._persist()` writes to `market_regime_memory` — no `scout_signals` insert
- `LiquidityScout._persist()` writes to `liquidity_intelligence` — no `scout_signals` insert
- `CorrelationScout._persist()` writes to `correlation_memory` — no `scout_signals` insert
- `ExecutionScout._persist()` writes to `execution_intelligence` — no `scout_signals` insert
- `RedditScout._persist_signals()` writes to `external_scout_memory` — no `scout_signals` insert
- Same for all other external scouts

**Impact:** AntiPoisoningEngine queries `scout_signals` and always finds 0 rows — it is **effectively deaf** and cannot detect:
- Signal burst spam (Section 22A)
- Coordinated attacks (Section 22B)
- Stale contradictions (Section 22C)

Similarly, `SourceReliabilityEngine` queries `scout_signal_attribution` which is also empty.

### Root Cause #2 — External Scouts DNS Blocked (Environment-Specific)

**All 6 external scouts cannot resolve DNS for their target APIs** — this is an environment-specific limitation of this local dev environment. Production/staging environments with working DNS would resolve this automatically.

| Scout | Target | Error |
|-------|--------|-------|
| RedditScout | `reddit.com` | DNS resolution failed |
| NewsIntelligenceEngine | `feeds.finance.yahoo.com` | DNS resolution failed |
| YouTubeScout | `youtube.com` | DNS resolution failed |
| DiscordScout | `discord.com` | DNS resolution failed |
| PodcastScout | `podcastindex.org` | DNS resolution failed |
| CompetitionScout | `kaggle.com` | DNS resolution failed |

**Result:** `external_scout_memory` has 0 rows. Even if the pipeline were fixed, external signals would not flow.

**Recommendation:** For Phase 25 in this environment, activate internal scouts only. External scouts can be wired into the same pipeline (code changes ready) but will only populate `scout_signals` in environments with network access.

### Root Cause #3 — No Influence Pipeline Exists

**Even if signals were flowing, nothing consumes them to modulate system behavior.**

The current architecture has:
- `ScoutSynthesisEngine` reads internal scout data and writes to `scout_synthesis_log` (0 rows — never called)
- `PortfolioIntelligenceEngine` reads `get_latest_scout_intelligence()` for regime-adjusted weights
- `IdeatorAgentV2` has NO scout influence
- `MutatorAgent` has NO scout influence
- `ExecutionGateway` has occasional scout regime read but no structured pipeline

**Result:** Scout intelligence has zero economic influence on the organism.

---

## 3. Pipeline Gap Analysis

```
                    CURRENT STATE                          DESIRED STATE
                    =============                          =============

RegimeScout ──────→ market_regime_memory          RegimeScout ──────→ market_regime_memory
                                                                    └──→ scout_signals (NEW)
LiquidityScout ───→ liquidity_intelligence        LiquidityScout ───→ liquidity_intelligence
                                                                    └──→ scout_signals (NEW)
CorrelationScout ─→ correlation_memory            CorrelationScout ─→ correlation_memory
                                                                    └──→ scout_signals (NEW)
ExecutionScout ───→ execution_intelligence        ExecutionScout ───→ execution_intelligence
                                                                    └──→ scout_signals (NEW)
External Scouts ──→ external_scout_memory (0)     External Scouts ──→ external_scout_memory (SIM)
                                                                    └──→ scout_signals (NEW)

scout_signals ────→ ∅ (0 rows)                    scout_signals ────→ AntiPoisoningEngine
                                                                    └──→ SourceReliabilityEngine
                                                                     └──→ ScoutSynthesisEngine

ScoutSynthesisEngine → ∅ (0 rows)                 ScoutSynthesis ───→ IdeatorAgentV2 (archetype bias)
                                                                    └──→ MutatorAgent (weighting)
                                                                     └──→ RiskController (sizing)
                                                                      └──→ scout_synthesis_log

AntiPoisoningEngine → ∅ (scout_poison = 0)        AntiPoisoning ────→ scout_poison_quarantine
                                                                     └──→ source_performance_log
```

---

## 4. Detailed Phase 25 Execution Plan

### Phase 25A — Ingestion Validation (DIAGNOSTIC ONLY — NO CHANGES)

**Objective:** Verify connectivity and data flow for all scouts.

**Actions:** Already complete — see sections 1-3 above.

**Deliverable:** This document (PHASE25_READINESS_ASSESSMENT.md)

---

### Phase 25B-C — Signal Pipeline Fix + Debug Mode (CODE CHANGES)

**Objective:** Make ALL scouts write to `scout_signals` and add debug signal tracking.

**Approach A: Per-scout modification (touches 6+ files)**
- Add `write_scout_signal()` to `TimescaleClient`
- Modify each scout's `_persist()` to call it
- +3-5 lines per scout file

**Approach B (RECOMMENDED): Auto-mirror in `_execute_insert()` — single change**
- Modify `TimescaleClient._execute_insert()` to detect scout table inserts (by table name pattern) and **automatically** mirror a normalized entry to `scout_signals`
- Pros: One change, future-proofs all existing and new scouts, no need to touch individual scout files
- Cons: Slightly more complex logic in `_execute_insert()`

**Recommended: Approach B** — Modify `_execute_insert()` to auto-write to `scout_signals` when the target table matches any known scout table. This ensures ALL scouts automatically contribute signals without per-file changes.

**Files to modify (Approach B — 2 files):**

1. **`data/storage/timescale_client.py`**
   - Add `async def _write_scout_signal(source, symbol, signal_type, confidence, signal_data)` method
   - Modify `_execute_insert()` to detect scout inserts and auto-mirror to `scout_signals`

2. **`data/storage/timescale_client.py`** (same file)
   - Add `scout_signal_debug_log` table creation in `connect()`
   - Add global `_signal_debug_mode` flag (default `False`)
   - In `_execute_insert()`, when debug mode is ON, log all rejected/candidate/scored signals to `scout_signal_debug_log`

**Changes required:** ~40-50 lines, 1 file (timescale_client.py)

---

### Phase 25D — Scout Influence Activation (CODE CHANGES)

**Objective:** Wire scout signals into Ideator, Mutator, and RiskController.

#### 25D-1: IdeatorAgent Influence (HIGHEST IMPACT)

**Files to modify:**

1. **`agents/l2_strategy/ideator_agent_v2.py`**
   - Add `_enrich_with_scout_context()` method that:
     - Reads latest regime/liquidity/correlation data from DB
     - Builds a `scout_context` string with current market state
     - Appends to the generation prompt as enriched context
   - Modify `_generate_strategies()` or equivalent to call `_enrich_with_scout_context()`

**Example influence:** `"Scout regime: NVDA mean-reverting in high volatility. Bias generation toward mean-reversion archetypes with tighter stops."`

#### 25D-2: MutatorAgent Influence (MEDIUM IMPACT)

**Files to modify:**

1. **`agents/l3_backtest/mutator_agent.py`** (or equivalent)
   - Read regime/liquidity from DB
   - Adjust mutation weights: e.g., high volatility → bias toward stop-loss parameter mutations
   - Log the adjustment with before/after weights

**Example influence:** `"Volatility regime = high_vol. Mutation weight for 'stop_loss_adjustment' increased 2x. Entropy penalty for breakout mutations applied."`

#### 25D-3: RiskController Influence (SAFETY GATE)

**Files to modify:**

1. **`agents/l4_risk/risk_controller.py`** (or equivalent)
   - Read liquidity/correlation data from scouts
   - If liquidity = dangerous, reduce `max_single_position_pct`
   - If correlation spike detected, increase diversification requirement

**Example influence:** `"Liquidity scout: BTCUSDT liquidity = dangerous (score=0). Reducing max position size from 15% to 8%."`

---

### Phase 25E — Predictive Value Testing (NEW SCRIPT)

**Objective:** Run controlled A/B experiment comparing scout-off vs scout-on.

**New file:** `scripts/ab_test_scout_influence.py`

**Design:**
- Run 2 cycles of strategy generation:
  - **TEST A:** Scouts OFF (baseline, no context)
  - **TEST B:** Scouts ON (with enriched context)
- Compare:
  - Validation pass rate
  - Sharpe distribution
  - Mutation survival rate
  - Strategy diversity (entropy)

---

### Phase 25F — Anti-Poisoning Validation (NEW SCRIPT)

**Objective:** Inject controlled adversarial noise and verify quarantine.

**New file:** `scripts/inject_adversarial_scout_signals.py`

**Design:**
- Inject burst spam: 50 identical signals for same symbol in 1 minute
- Inject coordinated attack: 5 low-trust sources, same symbol
- Inject contradictory signals: opposite sentiment for same asset
- Verify:
  - `scout_poison_quarantine` populated
  - `source_performance_log.trust` decreased
  - Identity of quarantined sources matches injected sources

---

### Phase 25G — Economic Attribution (CODE CHANGES + NEW QUERIES)

**Objective:** Track every signal from creation to economic outcome.

**Files to modify:**

1. **`data/storage/timescale_client.py`** — Add:
   - `scout_attribution_lineage` table
   - `write_signal_attribution()` method
   - `get_source_sharpe_contribution()` query

2. **Each scout's `_persist()`** — After writing to `scout_signals`, write attribution link

**Attribution chain:** `signal_id → strategy_id → backtest_id → trade → pnl`

---

### Phase 25H — 1-Hour Economic Activation Soak

**Command:** `python scripts/full_autonomous_cycle.py --duration-minutes 60`

**Monitoring:**
- Every 5 min: scout ingestion counts, signal candidates, trust/entropy evolution
- Every 10 min: direct DB queries on all scout tables
- At end: compare scout-on metrics vs baseline

**Success criteria:**
- `scout_signals` > 0
- Influence events logged
- Anti-poisoning active
- Attribution chains complete

---

## 5. Interaction Design — Phase 25D Influence Mechanics

### IdeatorAgent — Scout Context Injection

```
┌─────────────────────────────────────────────────────────┐
│                    Generation Prompt                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [STANDARD PROMPT TEMPLATE]                             │
│  "Generate a trading strategy for BTCUSDT..."          │
│                                                         │
│  [SCOUT ENRICHED CONTEXT] ← NEW                        │
│  "Current Market Context:                               │
│   - Volatility: high_vol (NVDA, BTC, ETH)              │
│   - Trend: choppy (SPY, QQQ) / mean_reverting (NVDA)   │
│   - Liquidity: dangerous (SPY, BTC) / excellent (ETH)  │
│   - Correlation: diversified (0.24) cluster=tech_heavy │
│                                                         │
│   Suggested archetype bias: mean_reversion              │
│   Suggested risk regime: cautious_position_sizing       │" │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### MutatorAgent — Regime-Conditioned Weighting

```
Current mutation weights (default):
  crossover: 0.15
  parameter_tweak: 0.25
  stop_loss_adjustment: 0.10
  regime_switch: 0.10
  → ... total = 1.0

Scout signal: volatility_regime = high_vol
Adjusted mutation weights:
  crossover: 0.10 (-0.05)
  parameter_tweak: 0.20 (-0.05)
  stop_loss_adjustment: 0.25 (+0.15) ← increased
  regime_switch: 0.15 (+0.05)
  → ... total = 1.0
```

### RiskController — Liquidity-Gated Sizing

```
Scout signal: liquidity_regime = dangerous
Action: max_single_position_pct = min(default, 15% * liquidity_score / 100)
Result: liquidity_score = 0 → max_position = 0% (no new positions)
        liquidity_score = 76 → max_position = 11.4%
```

---

## 6. Recommendation

**The system IS ready for Phase 25 execution.** All diagnostics are complete and the root causes are clearly identified. The changes required are:

| Phase | Files Changed | Lines Added | Complexity | Risk |
|-------|:------------:|:-----------:|:----------:|:----:|
| B-C | 1-2 files (Approach B) | ~60-80 lines | Low | Low |
| D | ~3 files | ~80-120 lines | Medium | Medium |
| E | 1 new file | ~200 lines | Medium | Low |
| F | 1 new file | ~150 lines | Low | Low |
| G | 2-3 files | ~60 lines | Low | Low |
| H | Monitor only | 0 | N/A | Low |

**Total:** ~8-12 files, ~550-650 new lines of code

**Recommendation:** Execute phases sequentially (B-C → D → E → F → G → H), running full tests after each phase.

---

## 7. Appendices

### Appendix A: Scout_signals Schema (Current)

```sql
CREATE TABLE IF NOT EXISTS scout_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT,
    symbol TEXT,
    signal_type TEXT,
    confidence_score NUMERIC DEFAULT 0.0,
    signal_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Appendix B: Key Code Locations

| Component | File Path |
|-----------|-----------|
| TimescaleClient | `data/storage/timescale_client.py` |
| RegimeScout | `agents/scouts/regime_scout.py` |
| LiquidityScout | `agents/scouts/liquidity_scout.py` |
| CorrelationScout | `agents/scouts/correlation_scout.py` |
| ExecutionScout | `agents/scouts/execution_scout.py` |
| RedditScout | `agents/scouts/reddit_scout.py` |
| NewsIntelligenceEngine | `agents/scouts/news_intelligence_engine.py` |
| ScoutSynthesisEngine | `agents/l7_meta/scout_synthesis_engine.py` |
| AntiPoisoningEngine | `agents/l7_meta/anti_poisoning_engine.py` |
| IdeatorAgentV2 | `agents/l2_strategy/ideator_agent_v2.py` |
| MetaOrchestrator | `core/meta_orchestrator.py` |
| TimescaleClient.connect() | `data/storage/timescale_client.py` (lines ~200-1500) |

---

*End of Phase 25 Readiness Assessment — Submitted for review before execution.*
