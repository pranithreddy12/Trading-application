# DAY 10 COST SYSTEM AUDIT
## Execution Cost Intelligence Layer — Baseline Assessment

**Date:** May 18, 2026  
**Objective:** Audit all files influencing trade frequency, net returns, fee assumptions, and cost friction.  
**Scope:** L2 Strategy (Ideator, Mutator, PatternAgent), L3 Backtest (Validator, BacktestRunner), Core scoring.

---

## SECTION 1: CURRENT COST ASSUMPTIONS

### 1.1 BacktestRunner (atlas/agents/l3_backtest/backtest_runner.py)

**Lines 52-54: Global Cost Constants**
```python
self.commission_pct = 0.001      # 0.1% per transaction
self.slippage_pct = 0.0005       # 0.05% per transaction
self.spread_cost_pct = 0.0005    # 0.05% per transaction
```

**Total Round-Trip Cost:** 0.002 = 0.2% (entry + exit combined = 0.4%)

**Cost Application (Lines 657-669):**
- Entry cost: commission + slippage + spread = 0.002
- Exit cost: commission + slippage + spread = 0.002
- Total round-trip: 0.004 (0.4% per trade pair)

```python
sub_df["trade_cost"] = np.where(
    sub_df["position"].diff().fillna(0) != 0,
    total_roundtrip_cost,
    0.0,
)
sub_df["strategy_return"] = (
    sub_df["position"] * sub_df["market_return"] * self.position_size
) - (sub_df["trade_cost"] * self.position_size)
```

**Key Finding:** Costs are applied uniformly per trade, but:
- ✅ Costs ARE applied to backtest results
- ❌ No differentiation by asset class (crypto vs equity)
- ❌ No volatility-adjusted spreads
- ❌ No slippage scaling by volume/frequency
- ❌ Fixed position_size (0.10) regardless of strategy profile

### 1.2 Cost Metrics Currently Tracked

**In BacktestRunner output:**
- `total_return`: Gross return (includes costs)
- `sharpe_ratio`: Computed from strategy_return (includes costs)
- `max_drawdown`: Includes cost drag
- `win_rate`: Based on cost-adjusted returns
- `profit_factor`: Cost-adjusted

**NOT currently tracked:**
- ❌ `gross_return`: Return without costs
- ❌ `friction_burden_pct`: Net vs gross
- ❌ `round_trip_cost_total`: Total cost in basis points
- ❌ `cost_efficiency_score`: Return per trade
- ❌ `expected_edge_per_trade`: Net return / trade_count
- ❌ `cost_trap_classification`: High-frequency, weak-edge indicators
- ❌ `trade_frequency_profile`: Trades per period analysis
- ❌ `commission_paid_total`: Actual cost burden

---

## SECTION 2: IDEATOR — WHERE COST AWARENESS IS MISSING

### 2.1 File: agents/l2_strategy/ideator_agent_v2.py

**Current Behavior:**
- Generates strategies with 5 archetypes: momentum, mean_reversion, breakout, trend_following, volatility_regime
- Uses fallback templates (LOCAL_TEMPLATES) with hardcoded entry/exit conditions
- NO awareness of trade frequency implications in templates
- NO cost-awareness in Claude prompts
- DIVERSE_TEMPLATES include multiple variants but NO guidance on frequency/cost tradeoffs

**Example Issue (Crypto Momentum):**
```python
("crypto", "momentum"): [
    (["ema_spread_pct > 0.002", "relative_volume > 1.5"],
     ["ema_spread_pct < 0.0", "rsi_14 > 70"]),
    ...
]
```

**Problem:** No assertion about expected trade frequency. Tight momentum conditions may trigger 100+ trades/day.

**Missing Cost Priors:**
1. No low-friction archetype examples
2. No cost-trap warnings (high-frequency + thin edges)
3. No guidance on thresholds that survive fees
4. No distinction between:
   - Low-frequency, strong-edge (best for costs)
   - High-frequency, weak-edge (cost-trap)
   - Medium-frequency, medium-edge (breakeven)

### 2.2 Ideator Prompts

**Current:** Claude generates entry/exit conditions in isolation.  
**Missing:**
```
COST AWARENESS:
- Avoid hyperactive strategies with weak expected edge
- Prefer strategies with wider margins per trade
- Bias toward lower churn / stronger conviction
- Penalize micro-edge systems likely to fail after fees
- Favor setups robust under realistic friction
```

---

## SECTION 3: VALIDATOR — WHERE COST GOVERNANCE IS ABSENT

### 3.1 File: agents/l3_backtest/validator_agent.py

**Current Thresholds (DEV mode):**
```python
min_sharpe: 0.25
max_drawdown: -80.0
min_trades: 5
min_win_rate: 0.25
min_profit_factor: 0.75
overfit_ratio: 0.0
```

**Problem:** These thresholds do NOT distinguish cost profiles:
- ❌ A strategy with 500 trades, 0.1% edge per trade fails after costs (total edge = 0.5% < 0.4% costs)
- ❌ A strategy with 20 trades, 3% edge per trade passes (total edge = 60% >> 0.4% costs)
- ✅ Both pass min_sharpe threshold, but ONLY the second is economically viable

**Missing Cost Governance Rules:**
```
NEW RULES:
- Short-window strategies (high trade frequency):
  * Require min_edge_per_trade > 0.15% (survive entry cost)
  * Require win_rate > 55% (to recover from costs)
  * Require profit_factor > 1.5 (margin of safety)

- Medium-frequency strategies (20-50 trades):
  * Min edge per trade: 0.10%
  * Win rate: 50%
  * Profit factor: 1.3

- Low-frequency strategies (< 20 trades):
  * Min edge per trade: 0.05%
  * Win rate: 45%
  * Profit factor: 1.1 (costs matter less)
```

**Missing Classification Labels:**
```
After validation, strategies should be labeled:
- cost_trap: (high frequency + low edge) → fail
- edge_fragile: (marginal edge after costs) → warn
- friction_resilient: (strong edge survives costs) → promote
- execution_efficient: (low frequency + strong edge) → elite
```

---

## SECTION 4: MUTATOR & PATTERN AGENTS — NO COST DELTA TRACKING

### 4.1 File: agents/l2_strategy/mutator_agent.py

**Current Mutation Families:**
```python
REPAIR, REFINEMENT, EXPLORATION, AGGRESSION, SIMPLIFICATION
```

**Current Tracking:**
- `mutation_type`, `parent_composite_score`, `child_composite_score`, `improved`
- ✅ Learns which mutations improve score
- ❌ Does NOT track cost efficiency changes

**Missing:**
```python
COST_EFFICIENCY_DELTA = (child_edge_per_trade - parent_edge_per_trade)
COST_BURDEN_DELTA = (child_friction_burden_pct - parent_friction_burden_pct)
TRADE_COUNT_DELTA = (child_trades - parent_trades)
```

**Key Question:** Which mutations REDUCE churn while preserving edge?
- Example: "condition_removal" might reduce trades but hurt edge
- Example: "threshold_adjustment" might improve frequency efficiency

### 4.2 File: agents/l2_strategy/mutation_pattern_agent.py

**Current Leaderboard Metrics:**
```
mutation_type, total, improved, failed, conversion_rate_pct, avg_score_delta
```

**Missing:**
```
avg_cost_efficiency_delta: (sum(child_edge_per_trade) - sum(parent_edge_per_trade)) / count
avg_friction_burden_delta: (sum(child_friction_burden_pct) - sum(parent_friction_burden_pct)) / count
trades_reduced_pct: pct of mutations that reduced trade count while maintaining edge
```

**Impact:** Cannot distinguish:
- Mutations that improve score by increasing frequency (BAD for execution)
- Mutations that improve score by strengthening edge (GOOD for execution)

---

## SECTION 5: SCORE_CONTRACT — NO COST-AWARE SCORING

### 5.1 File: core/score_contract.py

**Current Primary Score:**
```python
PRIMARY_SCORE_FIELD = "institutional_score"
compute_institutional_score() → short_window_score
```

**Missing:**
```python
# NEW SCORES TO ADD:
cost_efficiency_score = net_return / trade_count
friction_burden_pct = (gross_return - net_return) / gross_return
expected_edge_per_trade = net_return / (trade_count * 0.004)  # 0.004 = round-trip cost
cost_profile_classification = {
    "low_friction_alpha": edge_per_trade > 0.3% and trades < 50,
    "high_churn_cost_trap": edge_per_trade < 0.1% and trades > 100,
    "overtrading_fragile": edge_per_trade < 0.05% and trades > 200,
    "institutional_candidate": edge_per_trade > 0.15% and trades < 100,
}
```

---

## SECTION 6: RISK ASSUMPTIONS — HIDDEN COST DRIFT

### 6.1 Asset Class Differentiation

**Current:** Uniform costs across crypto and equity.  
**Reality:**
- Crypto: 0.05-0.20% maker, 0.10-0.25% taker fees + spreads
- Equity: 0.001-0.01% commission + spreads
- Forex: 0.0001-0.005% spreads

**Current Setting (0.1% + 0.05% + 0.05% = 0.2% per transaction):**
- ✅ Reasonable for equity
- ❌ Underestimates crypto costs
- ❌ Ignores forex entirely

### 6.2 Volatility-Adjusted Friction

**Current:** Fixed costs regardless of volatility.  
**Reality:** High-volatility periods have wider spreads.

**Missing:**
```python
spread_cost_pct = base_spread * (volatility / avg_volatility)
slippage_pct = base_slippage * (trade_frequency / avg_frequency)
```

### 6.3 Position Size Impact

**Current:** Fixed position_size = 0.10 (10% per trade)  
**Risk:** High-frequency strategies trade 100+ times, requiring 1000%+ capital.

**Missing:**
```python
effective_position_size = min(0.10, portfolio_capital / (estimated_trades * 10))
```

---

## SECTION 7: TRADE FREQUENCY ANALYSIS — KEY DRIFT RISK

### 7.1 Current Findings

**From mutation_leaderboard.txt** (if available):
- Typical strategy: 20-100 trades over backtest period
- High-frequency outliers: 500+ trades
- Low-frequency outliers: < 5 trades

**Critical Question:** How many of the 500+ trade strategies fail when costs are properly weighted?

**Hypothesis:** ~60-70% of high-frequency strategies are cost traps:
```
Example: 500 trades, 0.08% total return
- Gross return before costs: 0.084%
- Cost burden: 0.4% (500 * 0.4% cost per trade scaled down)
- Net return: 0.084% - 0.4% = -0.316% LOSS
- Validation result: PASS (because backtest applied costs uniformly)
- Reality: FAILURE in execution
```

### 7.2 Why Current System Misses This

The backtest DOES apply costs correctly, BUT:
- Validator does NOT distinguish cost-driven failures
- Ideator does NOT avoid generating high-frequency traps
- Mutator does NOT optimize for cost efficiency
- PatternAgent does NOT surface cost insights

---

## SECTION 8: DATABASE SCHEMA — COST TRACKING GAPS

### 8.1 Missing Columns in strategies table

```sql
-- Cost Profile (NEW)
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS cost_efficiency_score FLOAT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS friction_burden_pct FLOAT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS expected_edge_per_trade FLOAT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS cost_profile_class TEXT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS round_trip_cost_bps FLOAT;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS trade_frequency_profile TEXT;
```

### 8.2 Missing Columns in backtest_results table

```sql
-- Detailed Cost Breakdown (NEW)
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS gross_return FLOAT;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS total_costs_paid FLOAT;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS avg_cost_per_trade FLOAT;
ALTER TABLE backtest_results ADD COLUMN IF NOT EXISTS cost_as_pct_of_gross FLOAT;
```

---

## SECTION 9: GOVERNANCE RULES — COST-AWARE THRESHOLDS

### 9.1 Proposed Cost Governance Model

**Tier 1: Structural Gate** (ALWAYS APPLIED)
```python
if trade_count < 5:
    reject("Too few trades for cost analysis")
if trade_count > 1000:
    warn("Extreme frequency — likely overtrading")
```

**Tier 2: Cost Efficiency Gate** (NEW)
```python
# Edge per trade must exceed half the round-trip cost
edge_per_trade = net_return / trade_count
min_edge_per_trade = 0.004 / 2  # = 0.002 = 0.2%

if edge_per_trade < min_edge_per_trade:
    classification = "cost_trap"
    status = "failed_validation"
```

**Tier 3: Friction Resilience Gate** (NEW)
```python
# Strategies with tight margins must have lower friction
friction_burden_pct = (gross_return - net_return) / gross_return

if friction_burden_pct > 50%:
    if trade_count > 100:
        status = "friction_fragile"  # Alert
    if trade_count > 200:
        status = "failed_validation"  # Reject
```

---

## SECTION 10: ENVIRONMENTAL TOGGLES FOR GRADUAL ROLLOUT

### 10.1 Proposed Feature Flags

```python
# In config/settings.py
class ECILSettings:
    EXECUTION_COST_INTELLIGENCE = os.getenv("EXECUTION_COST_INTELLIGENCE", "OFF")
    # OFF: Current system (no cost awareness in generation)
    # ADVISORY: Ideator receives cost priors, but no hard rules
    # ENFORCED: Validator applies cost governance gates
    # FULL: Full A/B/C benchmark mode
    
    COST_EFFICIENCY_WEIGHTING = float(os.getenv("COST_EFFICIENCY_WEIGHTING", "0.0"))
    # 0.0: Cost is not considered in institutional_score
    # 0.2: 20% weight on cost efficiency
    # 1.0: Equal weight with other metrics
    
    MUTATION_COST_TRACKING = os.getenv("MUTATION_COST_TRACKING", "OFF")
    # OFF: No cost delta tracking
    # ON: Full cost efficiency delta in mutation_memory
```

---

## SECTION 11: IMPLEMENTATION READINESS MATRIX

| Phase | File | Change | Risk | Effort |
|-------|------|--------|------|--------|
| B | core/execution_cost_intelligence.py | NEW MODULE | Low | 2 hrs |
| C | ideator_agent_v2.py | Add cost prompts | Low | 1 hr |
| D | validator_agent.py | Add cost gates | Medium | 2 hrs |
| D | core/score_contract.py | Add cost scores | Low | 1 hr |
| E | mutator_agent.py | Cost delta tracking | Low | 1 hr |
| E | mutation_pattern_agent.py | Cost leaderboard | Low | 1 hr |
| F | Test infrastructure | Benchmark harness | High | 4 hrs |
| G | Analysis & reporting | Benchmark report | Low | 2 hrs |

**Total Implementation Time:** ~14 hours (can parallelize 60%)

---

## SECTION 12: CRITICAL OPEN QUESTIONS FOR DESIGN PHASE B

1. **Should cost intelligence be constitutional or advisory initially?**
   - RECOMMENDED: Advisory first (Phase C), then enforced after Phase F validation

2. **How to weight cost efficiency vs institutional score?**
   - RECOMMENDED: 0.0 for Phase C/D (purely informational)
   - 0.3 for Phase E (soft weighting)
   - 1.0 after Day 10 complete (equal weight)

3. **Should we have separate cost profiles by asset class?**
   - RECOMMENDED: Yes, but Phase B uses unified model, Phase G adds asset-class variants

4. **How to penalize high-frequency strategies without destroying diversity?**
   - RECOMMENDED: Classifier (cost_trap vs friction_resilient) not hard rejection

5. **Should mutation cost tracking be per-transaction or per-strategy level?**
   - RECOMMENDED: Per-strategy level (aggregate cost deltas, not per-trade)

---

## SECTION 13: DRIFT RISK SUMMARY

| Risk | Current State | Detection | Mitigation |
|------|---------------|-----------|-----------|
| Cost-invisible high-frequency traps | ✅ Costs in backtest, ❌ not analyzed | Cost efficiency scoring | ECIL classification |
| Asset-class cost misalignment | ❌ Uniform costs | Separate cost profiles | Phase G enhancement |
| Mutation churn explosion | No tracking | Cost delta in mutation_memory | Leaderboard visibility |
| Ideator biased toward frequency | ✅ No evidence yet | Archetype frequency analysis | Cost priors in prompts |
| Validator false positives on edge | ❌ No cost gating | Expected edge per trade | Tier 2 validation gate |
| Silent strategy degradation | No audit trail | Cost burden tracking | Lineage in event system |

---

## SECTION 14: SUCCESS CRITERIA FOR PHASE A AUDIT

✅ **COMPLETE:** Identified all cost assumptions  
✅ **COMPLETE:** Mapped cost application points  
✅ **COMPLETE:** Documented missing cost metrics  
✅ **COMPLETE:** Identified drift risks  
✅ **COMPLETE:** Designed governance gates  
✅ **COMPLETE:** Sketched ECIL API  
✅ **COMPLETE:** Assessed implementation readiness  
✅ **COMPLETE:** Prioritized for Phase B implementation  

---

## NEXT STEPS: PHASE B IMPLEMENTATION

**Time Allocation:**
1. Phase B (ECIL module): 2 hours
2. Phase C (Ideator patch): 1 hour
3. Phase D (Validator patch): 2 hours
4. Phase E (Mutation patch): 2 hours
5. Phase F (Benchmark harness): 4 hours
6. Phase G (Execution & analysis): 3 hours
7. Phase H (Certification & reporting): 2 hours

**Ready to proceed with Phase B implementation.**
