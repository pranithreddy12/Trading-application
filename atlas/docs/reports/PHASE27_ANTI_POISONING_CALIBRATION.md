# PHASE 27C -- ANTI-POISONING CALIBRATION
**Date:** 2026-05-23 20:25 UTC

---

## ROOT CAUSE

AntiPoisoningEngine used globally-thresholded burst detection that:
- Flagged normal scout cadence as "coordinated spam"
- Did not account for per-scout emission rate differences
- Collapsed trust to 0.0 during healthy ingestion (48+ signals/min)

## SOLUTION

### Per-Scout Burst Limits

`agents/l7_meta/anti_poisoning_engine.py` -- `PER_SCOUT_BURST_LIMITS` dict:

| Source | Limit (signals/hour) | Rationale |
|--------|---------------------|-----------|
| regime_scout | 300 | High cadence -- continuous regime tracking |
| liquidity_scout | 250 | Dense cadence -- continuous liquidity assessment |
| correlation_scout | 150 | Moderate -- correlation regime changes |
| execution_scout | 100 | Event-driven -- execution quality reports |
| default | 100 | Fallback for unknown sources |

### Cadence-Aware Rate Detection

Burst detection now checks both:
1. Total count exceeds per-scout limit
2. Per-minute rate exceeds 2x expected rate

This prevents false positives from bursty-but-normal activity.

### Trust Calibration (Phase 26H Carryover)

- Burst severity: 0.8 -> **0.3** (gentler response)
- Trust slash: severity*0.5 -> **severity*0.15** (much gentler)
- Initial trust floor in INSERT: 0.5 -> **0.9** (trust starts higher)
- Coordinated attack threshold: avg_trust < 0.6 -> **< 0.8** (more conservative)

### `_get_scout_burst_limit()` converted from async to sync

Simple dict lookup doesn't need async overhead.

## VERIFICATION

- Quarantine events captured: 0 (1h)
- Expected: far fewer false-positive quarantine events during healthy scout ingestion
