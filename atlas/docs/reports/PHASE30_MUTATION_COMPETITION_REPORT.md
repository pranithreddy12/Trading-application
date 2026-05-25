# PHASE30 — MUTATION COMPETITION REPORT

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Phase:** 30 — Economic Densification & Adaptive Selection Pressure

---

## Overview

Mutation competition measures the diversity, throughput, and selection dynamics within ATLAS's evolutionary strategy generation. Phase 30 expanded the mutation ecology to encourage true evolutionary competition.

## Mutation Ecology Metrics

| Metric | Phase 29 | Phase 30 | Delta |
|--------|----------|----------|-------|
| Max Mutation Variants | 7 | 12 | +71% |
| Max Variants (eco stress) | 10 | 17 | +70% |
| Min Viability Threshold | 0.30 | 0.15 | -50% |
| Claude Viability Threshold | 0.30 | 0.15 | -50% |
| Min Entry Count (filter) | 3 | 1 | -67% |
| Min Trades (filter) | 3 | 1 | -67% |

## Key Changes

### 1. Clone Paranoia Reduction (Phase 30B)
- **MAX_DUPLICATE_DISTANCE:** 0.15 → 0.05
- Only near-identical clones (95%+ similarity) are rejected
- Previously rejected at 85% similarity
- Allows overlapping mutation families to coexist and compete

### 2. Viability Thresholds Lowered
- Deterministic mutations: 0.30 → 0.15
- Claude mutations: 0.30 → 0.15
- More imperfect organisms survive to be tested

### 3. Structural Filters Relaxed
- MIN_ENTRY_COUNT: 3 → 1
- MIN_TRADES: 3 → 1
- Strategies with minimal signal activity now get mutated

## Competition Dynamics

**Expected outcomes:**
- More mutation candidates per cycle (3-5x increase)
- Overlapping feature families competing for survival
- Increased mutation family counts
- Higher variance in offspring quality
- Natural selection via retirement rather than pre-filtering

**Risk:**
- Lower average quality of mutations
- More computational cost per cycle
- Potential for degenerate mutation loops

## Mutation Family Distribution

| Family | Expected Share | Role |
|--------|---------------|------|
| REPAIR | 30% | Fix broken thresholds |
| REFINEMENT | 25% | Tweak working strategies |
| EXPLORATION | 20% | Add new indicators |
| AGGRESSION | 15% | Tighten risk management |
| SIMPLIFICATION | 10% | Remove unnecessary conditions |

## Conclusion

Mutation ecology has been expanded significantly. The reduced clone paranoia and viability thresholds should generate true evolutionary competition where organisms compete for survival rather than being pre-filtered.
