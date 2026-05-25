# PHASE 31 — REGIME SPECIALIZATION REPORT

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Phase:** 31C — Regime Specialization Engine

---

## Objective

Implement persistent regime profiling for each organism. Prove adaptive contextual specialization — that organisms develop clear regime affinities over time.

---

## Methodology

The `RegimeSpecializationEngine` (L7 meta-agent) runs every 30 minutes and:

1. Fetches all active organisms with full backtest metadata
2. Computes six regime dimensions per organism:
   - **Bull survivability:** Sharpe, CAGR, profit factor, controlled drawdown
   - **Bear survivability:** Low drawdown, positive sortino, profit factor > 1
   - **Ranging survivability:** High win rate, moderate profit factor, low volatility
   - **Volatility tolerance:** Handles high std deviation, positive Sharpe
   - **Liquidity sensitivity:** Trade count as proxy
   - **Archetype-regime alignment:** Ideal regime map for each strategy archetype
3. Assigns primary regime affinity (bull/bear/ranging)
4. Computes profile confidence based on trade count, Sharpe, and score stability
5. Generates ecosystem-level regime specialization distribution
6. Persists to `organism_regime_profile` and `regime_specialization_aggregate`

### Ideal Regime Archetype Map
| Archetype | Best Regime | Second Best |
|-----------|-------------|-------------|
| Momentum | trending | bull_market |
| Mean Reversion | ranging | low_vol |
| Breakout | trending | bull_market |
| Volatility | high_vol | trending |
| Scalping | low_vol | ranging |

---

## Findings

### Regime Affinity Distribution

| Affinity | Count | % of Population |
|----------|-------|-----------------|
| Bull Market | Pipeline-dependent | - |
| Bear Market | Pipeline-dependent | - |
| Ranging | Pipeline-dependent | - |

### Organism Regime Profiles

Each tracked organism receives:
- **Bull survivability score** (0-1)
- **Bear survivability score** (0-1)
- **Ranging survivability score** (0-1)
- **Volatility tolerance score** (0-1)
- **Liquidity sensitivity score** (0-1)
- **Archetype-regime alignment score** (0-1)
- **Primary affinity classification**
- **Profile confidence** (0-1)

### Confidence Metrics

Profile confidence increases with:
- More trades (> 50 trades = higher confidence)
- Higher Sharpe ratio (> 2.0 = higher confidence)
- Higher composite score (> 50 = higher confidence)

---

## Conclusion

Regime profiling infrastructure is operational. Each organism now tracks six regime dimensions with confidence-weighted scores. As the population matures through multiple market conditions, regime specialization patterns will become statistically significant.

---

## Next Steps

1. Monitor regime stability over 12-hour soak
2. Feed regime profiles into PortfolioEvolutionPressure
3. Cross-reference with regime stress survival data
4. Track whether regime-specialized organisms outperform generalists
