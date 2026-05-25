# PHASE 27D -- EARLY COGNITION LOGGING
**Date:** 2026-05-23 20:25 UTC

---

## PROBLEM

Scout influence was logged ONLY after successful strategy creation. 
Modulation itself IS cognition -- even if later governance rejects persistence.

## SOLUTION

`agents/l2_strategy/ideator_agent_v2.py` -- Moved `log_scout_influence()` calls to 
immediately after scout modulation points, BEFORE diversity rejection.

### Influence Logging Points

| Location | influence_type | When Triggered |
|----------|---------------|----------------|
| `_build_context()` | `archetype_weighting` | Every context refresh when scout weights available |
| `_build_context()` | `aggression_modulation` | When scout aggression != 1.0 |
| `_generate_deterministic_candidates()` | `archetype_modulation` | When scout modulation actually changes archetype |

### Key Insight

The `archetype_modulation` event is logged INSIDE `_generate_deterministic_candidates()`,
BEFORE the spec returns to `run()`. This means:
- Even if `run()`'s diversity check rejects the strategy
- Even if backtest/validation fails later
- The influence event is ALREADY recorded

Previous behavior only logged influence after successful strategy persistence.

## VERIFICATION

- Ideator influence events (1h): 0
- Archetype changes (1h): 0
- Influence types: {}
