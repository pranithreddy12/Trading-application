# DAY 10 OPEN QUESTIONS — RESOLUTION
## Strategic Answers to 5 Critical Day 10 Design Questions

**Date:** May 18, 2026  
**Author:** Lead Systems Architect  
**Scope:** Governance, design, and roadmap decisions for Day 10 and beyond

---

## QUESTION 1: Trade Frequency Bands & Acceptability

**Original Question:**
"What trade frequency bands are acceptable for:
- Crypto scalp
- Crypto swing
- Equity intraday
- Equity swing?"

### ANSWER

**Crypto Scalp Trading (High Frequency)**

**Definition:** >100 trades over backtest period  
**Duration:** 1m bars (minute-level signals)  
**Acceptance Criteria:**
- Min edge per trade: 40 bps (4x round-trip cost of 10 bps)
- Min win rate: 54% (need 2:1 winner:loser ratio to cover costs)
- Min profit factor: 1.8
- Max acceptable trade count: 500 (extreme frequency = data mining risk)
- Risk level: HIGH (requires institutional-grade slippage models)

**Rationale:**
- Crypto round-trip cost ≈ 40 bps (Binance taker)
- Scalping requires 40 bps edge/trade to break even after costs
- Win rate must be >54% to account for friction on winners
- Profit factor 1.8 = 1.8x gross profit vs gross loss (safety margin)

**Example Profile:**
```
Strategy: Crypto scalp momentum
Trades: 250 over 30-day backtest
Net return: 2.5% (250 trades × 0.01% edge/trade)
Cost burden: 0.15% (250 × 40 bps × 0.01 size)
Friction resilience: MEDIUM (edge only 2.5x cost)
Recommendation: ACCEPT with caution, real-money allocation 2-5%
```

---

**Crypto Swing Trading (Medium Frequency)**

**Definition:** 50-100 trades over backtest period  
**Duration:** 15m-1h bars (hour-level signals)  
**Acceptance Criteria:**
- Min edge per trade: 25 bps (2.5x round-trip cost)
- Min win rate: 52%
- Min profit factor: 1.5
- Max acceptable trade count: 150
- Risk level: MEDIUM (better slippage profile)

**Rationale:**
- Longer timeframes = wider spreads = can execute closer to fair value
- 25 bps edge/trade = 62% margin of safety vs 40 bps cost
- Win rate 52% more achievable (fewer micro-moves)
- Profit factor 1.5 acceptable (established strategy profile)

**Example Profile:**
```
Strategy: Crypto swing mean reversion
Trades: 75 over 30-day backtest
Net return: 1.88% (75 × 25 bps edge × 0.01 size)
Cost burden: 0.12% (75 × 40 bps)
Friction resilience: MEDIUM-HIGH (edge 2.5x cost)
Recommendation: ACCEPT, real-money allocation 10-20%
```

---

**Equity Intraday Trading (Medium Frequency)**

**Definition:** 50-100 trades over backtest period  
**Duration:** 5m-15m bars (intraday signals)  
**Acceptance Criteria:**
- Min edge per trade: 10 bps (10x round-trip cost of 1 bps for equity)
- Min win rate: 51%
- Min profit factor: 1.3
- Max acceptable trade count: 150
- Risk level: MEDIUM (liquid markets, tight spreads)

**Rationale:**
- Equity round-trip cost ≈ 1 bps (low commission environment)
- 10 bps edge/trade = 10x cost buffer (strong resilience)
- Win rate 51% achievable (favorable cost dynamics)
- Profit factor 1.3 acceptable (costs well below profit margin)

**Example Profile:**
```
Strategy: Equity intraday RSI scalp
Trades: 80 over 20-day backtest (4 trading hours/day)
Net return: 0.80% (80 × 10 bps edge × 0.01 size)
Cost burden: 0.008% (80 × 1 bps)
Friction resilience: HIGH (edge 10x cost)
Recommendation: ACCEPT, real-money allocation 25-40%
```

---

**Equity Swing Trading (Low Frequency)**

**Definition:** <50 trades over backtest period  
**Duration:** Daily-weekly bars  
**Acceptance Criteria:**
- Min edge per trade: 5 bps (5x round-trip cost)
- Min win rate: 50%
- Min profit factor: 1.1
- Max acceptable trade count: 50
- Risk level: LOW (cost almost irrelevant)

**Rationale:**
- Lower frequency = costs < 5% of total return (negligible)
- 5 bps edge/trade = 5x cost buffer (conservative)
- Win rate 50% acceptable (cost risk minimal)
- Profit factor 1.1 = breakeven design (costs don't threaten profitability)

**Example Profile:**
```
Strategy: Equity swing breakout
Trades: 35 over 60-day backtest (1-3 day holds)
Net return: 1.75% (35 × 50 bps edge × 0.01 size)
Cost burden: 0.035% (35 × 1 bps)
Friction resilience: VERY HIGH (edge 50x cost)
Recommendation: ACCEPT, real-money allocation 40-60%
```

---

### Summary Table

| Asset Class | Type | Frequency | Min Edge | Min WR | Min PF | Risk | Position Sizing |
|-------------|------|-----------|----------|--------|--------|------|-----------------|
| Crypto | Scalp | >100 | 40 bps | 54% | 1.8 | HIGH | 2-5% |
| Crypto | Swing | 50-100 | 25 bps | 52% | 1.5 | MED | 10-20% |
| Equity | Intraday | 50-100 | 10 bps | 51% | 1.3 | MED | 25-40% |
| Equity | Swing | <50 | 5 bps | 50% | 1.1 | LOW | 40-60% |

---

## QUESTION 2: Cost Burden Thresholds by Asset Class

**Original Question:**
"How should cost burden thresholds differ by asset class?"

### ANSWER

**Cost Burden Definition:**
Cost burden = (Gross return - Net return) / Gross return  
= Cost drag as % of potential return

---

**Crypto Cost Burden Thresholds**

**Acceptable Levels:**

| Return Profile | Max Friction Burden | Rationale |
|---------------|--------------------|-----------|
| Positive return (>0%) | <15% | Allow 15% of gains eaten by costs |
| Marginal return (0-1%) | <5% | Tight margin, costs threaten viability |
| Weak return (<0%) | REJECT | Costs pushed strategy into loss |

**Governance Rule:**
```
IF (gross_return > 0) AND (friction_burden_pct > 15%) THEN
    WARN: "Cost drag exceeds acceptable level"
    ACTION: Review for optimization
    
IF (gross_return < 1%) AND (friction_burden_pct > 5%) THEN
    FAIL: "Marginal return not robust to costs"
    ACTION: Reject strategy
    
IF (gross_return < 0) THEN
    FAIL: "Strategy already negative before costs"
    ACTION: Reject immediately
```

**Example:**
```
Strategy A: Crypto scalp
Gross return: 5.0%
Cost burden: 12.5% (0.625% costs)
Net return: 4.375%
Assessment: PASS (12.5% < 15% threshold)

Strategy B: Crypto scalp
Gross return: 1.0%
Cost burden: 8% (0.08% costs)
Net return: 0.92%
Assessment: FAIL (8% > 5% threshold for weak returns)
```

---

**Equity Cost Burden Thresholds**

**Acceptable Levels:**

| Return Profile | Max Friction Burden | Rationale |
|---------------|--------------------|-----------|
| Positive return (>0%) | <5% | Costs trivial for equities |
| Marginal return (0-1%) | <2% | Preserve micro-edge |
| Weak return (<0%) | REJECT | No second chance |

**Governance Rule:**
```
IF (gross_return > 0) AND (friction_burden_pct > 5%) THEN
    WARN: "Cost drag higher than typical for equities"
    
IF (gross_return < 1%) AND (friction_burden_pct > 2%) THEN
    FAIL: "Equity costs should be <1%, not this high"
    
IF (gross_return < 0) THEN
    FAIL: "Negative return unacceptable"
```

---

**Forex Cost Burden Thresholds**

**Acceptable Levels:**

| Return Profile | Max Friction Burden | Rationale |
|---------------|--------------------|-----------|
| Positive return (>0%) | <3% | Forex costs very low |
| Marginal return (0-1%) | <1% | Preserve micro-edge |
| Weak return (<0%) | REJECT | No recovery path |

---

### Implementation in Validator

```python
def check_cost_burden_acceptable(
    gross_return: float,
    net_return: float,
    asset_class: str,
) -> tuple[bool, str]:
    """
    Validate cost burden vs asset class thresholds.
    Returns (is_acceptable, reason_if_not)
    """
    friction = (gross_return - net_return) / gross_return if gross_return > 0 else 1.0
    
    if gross_return < 0:
        return False, "Gross return negative (costs irrelevant, strategy failed)"
    
    thresholds = {
        "crypto": {"positive": 0.15, "marginal": 0.05},
        "equity": {"positive": 0.05, "marginal": 0.02},
        "forex": {"positive": 0.03, "marginal": 0.01},
    }
    
    tier = thresholds.get(asset_class.lower(), thresholds["equity"])
    
    if gross_return > 0.01:  # >1% return
        threshold = tier["positive"]
    else:
        threshold = tier["marginal"]
    
    if friction > threshold:
        return False, f"Friction {friction:.1%} exceeds {threshold:.1%} for {asset_class}"
    
    return True, "Acceptable"
```

---

## QUESTION 3: Cost Intelligence — Advisory vs Constitutional?

**Original Question:**
"Should cost intelligence remain advisory or become constitutional after benchmark proof?"

### ANSWER

**RECOMMENDED APPROACH: Phased Escalation**

---

**Phase 1 — Day 10 Benchmark (TODAY - Starting 22:00 UTC)**

**Status:** ADVISORY  
**Mode:** Inform, not enforce  
**Enforcement:** 0%  

- Ideator receives cost priors but Claude not penalized for ignoring
- Validator flags cost profiles but doesn't fail strategies
- Mutation tracks cost deltas but doesn't modify priority
- Dashboard shows cost metrics but doesn't hide high-cost strategies
- Rationale: Gather baseline data, prove cost intelligence works

**Expected Cohort Outcomes:**
- day10_control: High cost trap %, lower validated rate
- day10_mutation: Medium improvement, cost-neutral  
- day10_cost: Much lower cost trap %, same validated rate (advisory only)
- day10_full: Best validated rate, lowest cost trap % (advisory + mutation)

---

**Phase 2 — Day 10 Evening (Post-Benchmark, IF results positive)**

**Status:** ENFORCED (Light)  
**Mode:** Enforce on new strategies only  
**Enforcement:** 30%  

- Ideator still receives cost priors (advisory for generation diversity)
- Validator REJECTS strategies classified as HIGH_CHURN_TRAP or OVERTRADING_FRAGILE
- Mutation prioritizes cost-reducing mutations (10% boost to conversion rate)
- Dashboard highlights cost-resilient candidates
- Rationale: Validate cost governance doesn't degrade exploration

**Expected Changes:**
- Validated rate may drop 2-5% (cost traps now rejected)
- Elite rate may rise 5-10% (better economic quality)
- Diversity maintained (archetypes still varied)

---

**Phase 3 — Day 11+ (Production Readiness)**

**Status:** CONSTITUTIONAL  
**Mode:** Enforce on all strategies  
**Enforcement:** 100%  

- Cost governance gates non-negotiable
- Ideator optimizes for cost AND pattern intelligence
- Validator ranks by institutional_score = f(quality, economics)
- Mutation engine cost-aware mutation selection
- Dashboard primary sort by cost_profile + institutional_score
- Rationale: ATLAS is now economically disciplined

---

### Benchmark Success Criteria for Escalation

**IF day10_full cohort shows:**

✅ Criteria 1: +15% validated rate vs day10_control  
✅ Criteria 2: <10% cost trap classification (vs >40% in control)  
✅ Criteria 3: +5% elite promotion vs day10_control  
✅ Criteria 4: No diversity regression (archetype variety maintained)  
✅ Criteria 5: Avg edge per trade +30% vs day10_cost (cost intel helps generation)  

**THEN:** Escalate to Phase 2 (enforced governance) same day  
**ELSE:** Keep advisory, investigate bottleneck, retry next benchmark

---

### Risk Mitigations

**Risk:** Cost governance too aggressive, destroys innovation

**Mitigation:**
- Keep cost priors advisory (don't block Claude exploration)
- Allow 5-10% of strategies to bypass cost gates (R&D allocation)
- Separate "production pool" (cost-governed) from "research pool" (advisory)

**Risk:** Benchmark shows cost intelligence helps, but not enough

**Mitigation:**
- Combine with other Day 10 features (risk awareness, pattern intelligence)
- Iterate cost model (maybe 40 bps too pessimistic?)
- Extend Phase 1 duration to gather more data

---

## QUESTION 4: Minimum Deployment Score

**Original Question:**
"What minimum deployment score qualifies a strategy for real paper deployment?"

### ANSWER

**Deployment Readiness Score (NEW METRIC)**

**Formula:**

```
deployment_readiness = (
    institutional_score * 0.40 +      # Quality score (0-100)
    cost_efficiency_score * 100 * 0.30 +  # Edge per trade (in basis points)
    friction_resilience * 100 * 0.20 +    # Cost survivability (0-1 scale)
    diversification_score * 100 * 0.10    # Pattern diversity (0-1 scale)
)
```

---

**Deployment Tiers**

| Tier | Score Range | Real Money | Daily Limit | Max Position | Hold |
|------|-------------|-----------|------------|--------------|------|
| ELITE | 85-100 | YES | Unlimited | 100% | Indefinite |
| PRODUCTION | 70-84 | YES | $10k | 50% | 30 days |
| CANDIDATE | 60-69 | NO (Paper) | N/A | N/A | Paper trade |
| RESEARCH | <60 | NO | N/A | N/A | Backtest only |

---

**Minimum Scores by Asset Class & Frequency**

| Type | Min Score | Rationale |
|------|-----------|-----------|
| Crypto Scalp | 80 | High risk, need PRODUCTION tier minimum |
| Crypto Swing | 75 | Medium risk |
| Equity Intraday | 75 | Medium risk |
| Equity Swing | 70 | Low risk, PRODUCTION tier acceptable |
| Long-term (Algo) | 60 | Very low cost risk |

---

**Individual Metric Minimums (All must pass)**

| Metric | ELITE | PROD | CANDIDATE |
|--------|-------|------|-----------|
| Institutional Score | ≥75 | ≥65 | ≥55 |
| Edge/Trade (bps) | ≥30 | ≥15 | ≥5 |
| Friction Resilience | ≥0.7 | ≥0.5 | ≥0.3 |
| Win Rate | ≥0.55 | ≥0.50 | ≥0.45 |
| Profit Factor | ≥1.5 | ≥1.3 | ≥1.1 |
| Max Drawdown | ≤-20% | ≤-30% | ≤-50% |
| Sharpe Ratio | ≥1.5 | ≥1.0 | ≥0.5 |
| Cost Trap Prob | <5% | <10% | <20% |

---

**Governance Implementation**

```python
class DeploymentReadiness:
    ELITE = 85
    PRODUCTION = 70
    CANDIDATE = 60
    RESEARCH = 0
    
    @staticmethod
    def compute_score(strategy: dict) -> float:
        inst_score = strategy.get("institutional_score", 0)
        cost_eff = strategy.get("cost_efficiency_score", 0) * 100
        friction_res = strategy.get("friction_resilience", 0) * 100
        diversity = strategy.get("diversity_score", 0) * 100
        
        return (
            inst_score * 0.40 +
            min(cost_eff, 100) * 0.30 +  # Cap at 100
            min(friction_res, 100) * 0.20 +
            min(diversity, 100) * 0.10
        )
    
    @staticmethod
    def get_tier(score: float, asset_class: str) -> str:
        minimums = {
            "crypto_scalp": 80,
            "crypto_swing": 75,
            "equity_intraday": 75,
            "equity_swing": 70,
        }
        min_required = minimums.get(asset_class, 70)
        
        if score >= 85:
            return "ELITE"
        elif score >= min_required:
            return "PRODUCTION"
        elif score >= 60:
            return "CANDIDATE"
        else:
            return "RESEARCH"
```

---

**Real-Money Deployment Workflow**

```
1. Strategy backtested, validated
2. Compute deployment_readiness score
3. If score >= PRODUCTION:
   - Add to deployment queue
   - Allocate capital based on tier
   - Set position limits
   - Configure kill switch + monitoring
4. Start with 1-2% of portfolio
5. Increase gradually (daily_profit_limit + monthly_cap)
6. Rollback if Sharpe degrades >20% or drawdown exceeds limit
```

---

## QUESTION 5: Day 10 → Day 11+ Roadmap Impact

**Original Question:**
"How should Day 10 alter Day 11+ roadmap?"

### ANSWER

**Day 10 Success Scenarios & Roadmap Shifts**

---

**Scenario A: Cost Intelligence Proves High Impact (>20% quality improvement)**

**Then:** ACCELERATE Scout expansion + Alpaca cert

**Day 11 Priority:**
1. Scout Network (multi-symbol intelligence)
2. Alpaca paper trading validation
3. Multi-broker support (Interactive Brokers)
4. Enhanced risk models (cost-aware position sizing)

**Rationale:** If cost awareness drives 20%+ better strategies, Scout can scale to hundreds of symbols with economic confidence.

**Timeline:** Scout launch (Day 12-13), Alpaca cert (Day 14-15)

---

**Scenario B: Cost Intelligence Shows Modest Impact (10-15% improvement)**

**Then:** INTEGRATE cost awareness into existing features, then expand

**Day 11 Priority:**
1. Consolidate cost governance across all modules
2. Dashboard economics visualization
3. 48-hour soak run with cost monitoring
4. Gradual Scout expansion (50 symbols first)

**Timeline:** Extended stabilization (Day 12-14), Scout launch (Day 15)

---

**Scenario C: Cost Intelligence Shows Minimal Impact (<10% improvement)**

**Then:** INVESTIGATE cost model assumptions, revisit generation strategy

**Day 11 Priority:**
1. Root cause analysis (cost assumptions vs reality)
2. Alternative cost models (market microstructure)
3. Hybrid generation (combine cost + diversity + pattern)
4. Focus on other Day 10 features (copy trader hardening)

**Timeline:** Debug phase (Day 11-12), Rebaseline (Day 13), Resume roadmap (Day 14+)

---

### Universal Changes (All Scenarios)

**Tier 1 — Non-Negotiable (Day 11)**

1. ✅ 48-hour autonomous ops soak + certification
2. ✅ Kill switch stress testing + restart validation
3. ✅ Event lineage completeness audit
4. ✅ Schema drift monitoring deployment
5. ✅ Cost model live validation (pre-paper trading)

**Tier 2 — Conditional (Day 12-14)**

1. Scout expansion (size depends on Scenario)
2. Dashboard economics features
3. API cost-analysis endpoints
4. Real-money deployment framework setup

**Tier 3 — Stretch (Day 15+)**

1. Multi-broker support
2. Advanced risk models
3. Feature store expansion (liquidity, regime)
4. Scout intelligence aggregation

---

### Roadmap Revision Logic

```
deployment_readiness_day10 = compute_score(...)
improvement_vs_baseline = (
    day10_full_validated_rate / day10_control_validated_rate
)

IF improvement_vs_baseline > 1.2 AND deployment_readiness > 75:
    # Scenario A: Accelerate expansion
    accelerate_scout_expansion()
    prioritize_alpaca_certification()
    
ELIF improvement_vs_baseline > 1.1 AND deployment_readiness > 70:
    # Scenario B: Integrate and expand gradually
    integrate_cost_governance()
    launch_dashboard_economics()
    gradual_scout_expansion()
    
ELSE:
    # Scenario C: Debug and stabilize
    analyze_cost_model()
    revisit_generation_strategy()
    focus_on_operations_hardening()
```

---

## DECISION SUMMARY TABLE

| Question | Answer | Timing | Impact |
|----------|--------|--------|--------|
| 1. Frequency bands | 4 bands defined with thresholds | Immediate | Validator governance |
| 2. Cost thresholds | Asset-class specific friction limits | Immediate | Validator gates |
| 3. Advisory vs constitutional | Phased: advisory → enforced | Day 10 → Day 11 | Governance escalation |
| 4. Deployment score | 85-100 ELITE, 70-84 PROD, <70 RESEARCH | Day 11 | Real-money gating |
| 5. Roadmap impact | Conditional on benchmark results | Day 10 → Day 11 | Scout/Alpaca decisions |

---

**Document:** DAY10_OPEN_QUESTIONS_RESOLUTION.md  
**Version:** 1.0  
**Authority:** Lead Systems Architect  
**Approval:** Pending Day 10 benchmark results
