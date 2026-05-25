# PHASE 27B -- ADAPTIVE DIVERSITY GOVERNANCE
**Date:** 2026-05-23 20:25 UTC

---

## PROBLEM

Previous diversity logic was:
- Globally static (fixed 0.70 threshold)
- Over-constrained (same threshold for all market regimes)
- Regime-insensitive (no awareness of market conditions)
- Throughput-insensitive (same constraints regardless of strategy generation rate)

## SOLUTION

`agents/l2_strategy/ideator_agent_v2.py` -- `_compute_adaptive_threshold()` method added.

### Regime-Aware Thresholds

| Regime | Hard Threshold | Soft Threshold | Rationale |
|--------|---------------|----------------|-----------|
| high_vol / panic / trending | 0.80 | 0.65 | Wider exploration allowed |
| ranging / neutral | 0.65 | 0.50 | Tighter controls to avoid overfitting noise |
| oversold / overbought | 0.75 | 0.60 | Moderate relaxation for extreme regimes |

### Throughput-Aware Adjustment

| Strategy Throughput | Hard Adjustment | Soft Adjustment | Rationale |
|-------------------|----------------|----------------|-----------|
| < 5 strategies | +0.08 | +0.08 | Relax to encourage generation |
| > 30 strategies | -0.05 | -0.05 | Tighten to prevent saturation |

### Clamping

Both thresholds are clamped to sane ranges:
- Hard: [0.50, 0.90]
- Soft: [0.40, 0.80]

## VERIFICATION

The `_check_diversity` method receives `regime` and `strategy_throughput` parameters
from `_build_context`, which already has access to regime data and scout intelligence.
