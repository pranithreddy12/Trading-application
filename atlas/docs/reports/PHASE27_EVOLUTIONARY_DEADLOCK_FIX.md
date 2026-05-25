# PHASE 27A -- EVOLUTIONARY DEADLOCK REMEDIATION
**Date:** 2026-05-23 20:25 UTC

---

## ROOT CAUSE

Strategies with `code_failed`, `permanently_failed`, `invalidated`, and `obsolete` statuses
were poisoning the diversity search space. These stale organisms permanently occupied
archetype space, blocking future evolution and constraining adaptive search.

## FIXES APPLIED

### 1. Expanded Status Exclusion

`data/storage/timescale_client.py` -- `get_recent_feature_combos()` query now excludes:
- `code_failed` (failed code compilation)
- `permanently_failed` (irrecoverable failure)
- `invalidated` (replay-invalidated)
- `obsolete` (aged out)

Only strategies with status `= 'active'`, `= 'pending'`, or `NULL` are included in diversity anchoring.

**Old query:** `WHERE status IS DISTINCT FROM 'code_failed'`
**New query:** `WHERE (status NOT IN ('code_failed','permanently_failed','invalidated','obsolete') OR status IS NULL)`

### 2. Time-Decayed Diversity Weighting

Each strategy in the diversity comparison now gets a **time weight**:
- Recent strategies (within 24h): weight ~1.0
- 3-day-old strategies: weight ~0.57
- 7-day-old strategies: weight ~0.1 (minimum)

This naturally reduces the influence of stale strategies over time.

### 3. 7-Day Recency Cutoff

Strategies older than 7 days are excluded from diversity anchoring entirely.

### 4. DB Cleanup

- 23 stale `code_failed` strategies deleted from database
- `evolutionary_garbage_collection()` method added for ongoing maintenance

## VERIFICATION

- **Before fix:** 0 strategies could pass diversity checks (deadlocked by 23 stale entries)
- **After fix:** Diversity check compares against an empty/clean set -- new strategies can pass
- Stale strategies previously blocked momentum, mean_reversion, breakout, trend_following archetypes
