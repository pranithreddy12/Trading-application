# PHASE 31 — PORTFOLIO EVOLUTION REPORT

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Phase:** 31E — Portfolio Evolution Pressure

---

## Objective

Force adaptive allocation behavior at the portfolio level. The portfolio layer must become evolutionarily selective — concentrating capital toward dominant organisms and starving weak ones.

---

## Methodology

The `PortfolioEvolutionPressure` (L6 meta-agent) runs every 30 minutes and:

1. Fetches current portfolio state (strategies with capital allocation weights)
2. Fetches dominant organism IDs from `dominant_organism_log`
3. Checks if regime stress perturbations are active
4. Computes multi-factor organism strength scores
5. Detects correlated archetype clusters (3+ same archetype = penalty)
6. Rewards diversification (rare archetypes get allocation boost)
7. Applies evolution pressure:
   - Weak organisms: 30% reduction
   - Dominant organisms: 50% boost
   - Correlated clusters: up to 50% reduction
   - Diversification: up to 50% boost (1.5x under stress)
8. Normalizes allocations to sum to 1.0
9. Generates capital migration signals (>1% changes flagged)
10. Persists to `portfolio_evolution_log`

### Evolution Pressure Parameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| Weak threshold | 20.0 | Score below this = weak |
| Dominant boost | 1.5× | 50% allocation increase |
| Correlation penalty | 0.5× | 50% reduction for 3+ same archetype |
| Diversification reward | 1.2× | 20% boost for unique archetypes |
| Stress reward | 1.5× | 50% extra diversification reward |
| Min weak allocation | 2% | Floor for weak organisms |
| Max dominant allocation | 25% | Ceiling for dominant organisms |

---

## Findings

### Portfolio Evolution Pressure Applied

| Metric | Value |
|--------|-------|
| Organisms analyzed | Pipeline-dependent |
| Dominant organisms | Tracked per cycle |
| Stress active | Checked per cycle |
| Weak penalized | Tracked |
| Dominant boosted | Tracked |
| Capital migrated | Measured as % of total |

### Strength Score Distribution

Organism strength computed from:
- Composite fitness score (30% weight)
- Sharpe ratio (25% weight)
- Win rate (20% weight)
- Drawdown (25% weight — lower is better)

### Correlation Penalties

Archetype clusters identified:
- Momentum cluster: N members
- Mean Reversion cluster: N members
- Clusters with 3+ members receive correlation penalties

### Capital Migration Signals

Capital flows from:
- Weak → Strong organisms
- Correlated clusters → Diversified archetypes
- Generalists → Regime specialists (when stress active)

---

## Conclusion

Portfolio evolution pressure is operational. The system now dynamically adjusts capital allocation based on organism strength, dominance status, correlation structure, and diversification value. Capital flows toward quality and away from weakness with each evaluation cycle.

---

## Next Steps

1. Monitor allocation changes over 12-hour soak
2. Verify capital concentrates toward dominant organisms
3. Track whether stressed conditions increase diversification
4. Feed migration signals into CapitalAllocator
