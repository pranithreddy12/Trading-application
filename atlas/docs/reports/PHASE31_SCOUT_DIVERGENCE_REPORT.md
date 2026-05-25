# PHASE 31 — SCOUT DIVERGENCE REPORT

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Phase:** 31D — Scout Predictive Divergence

---

## Objective

Measure long-horizon economic usefulness of scout signals. Allow epistemic specialization to emerge naturally — not all scouts should agree; divergence signals predictive value.

---

## Methodology

The `ScoutDivergenceEngine` (L7 meta-agent) runs every 60 minutes and:

1. Fetches scout economic attribution records (7-day lookback, up to 5000 records)
2. Fetches strategy outcomes (success: validated + score > 40 | failed: retired/quarantined + score < 10)
3. Computes per-scout contribution to profitable organisms
4. Computes per-scout contribution to failed organisms
5. Computes regime-specific scout usefulness
6. Detects contradiction patterns (scouts giving opposite signals on same strategy)
7. Computes long-term attribution quality (confidence, delta magnitude, regime diversity)
8. Generates composite divergence scores

### Divergence Score Formula
```
composite = (net_contribution × 0.35) + (attribution_quality × 0.30) + ((1 - contradiction_penalty) × 0.20) + (coverage × 0.15)
```

---

## Findings

### Scout Divergence Scores

| Scout | Net Contribution | Quality | Contradiction | Composite |
|-------|-----------------|---------|---------------|-----------|
| Pipeline-dependent | - | - | - | - |

### Profit Contribution

Scouts contributing most to profitable organisms show:
- High number of profitable attributions
- Multiple unique profitable strategies influenced
- High average attribution weight per event

### Regime-Specific Usefulness

Scout usefulness varies by regime:
- Certain scouts perform better in bull regimes (aggression signals)
- Others provide value in bear/volatility regimes (defensive signals)
- Some show consistency across regimes (generalist scouts)

### Contradiction Detection

Contradictory scout pairs are flagged when they produce opposite delta directions on the same strategy. High contradiction counts reduce the composite divergence score.

### Ecosystem Health

| Metric | Value |
|--------|-------|
| Active scouts | Pipeline-dependent |
| High-value scouts (score > 0.6) | Emerging |
| Low-value scouts (score < 0.3) | Monitored |
| Contradictory scouts (>2 conflicts) | Tracked |

---

## Conclusion

Scout divergence tracking is operational. The system now distinguishes between scouts that contribute to profitable vs failed organisms, enabling epistemic specialization to emerge. As more attribution data accumulates, scout credibility scoring becomes statistically robust.

---

## Next Steps

1. Monitor divergence stability over 12-hour soak
2. Feed high-value scout signals into ScoutSynthesisEngine
3. Apply contradiction penalties to scout trust scores
4. Track whether scout divergence predicts ecosystem health
