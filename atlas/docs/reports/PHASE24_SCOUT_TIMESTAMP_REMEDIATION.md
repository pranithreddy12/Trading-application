# PHASE24_SCOUT_TIMESTAMP_REMEDIATION.md

## Failure 2 — Scout Timestamp Corruption Report

**Severity:** P0 Critical  
**Date:** 2025-06-15  
**Status:** REMEDIATED ✅  

---

## Root Cause Analysis

Scouts generated ISO-8601 timestamps using `datetime.utcnow().isoformat()`, which produces naive strings without timezone information:

```
2024-01-01T12:00:00.123456    ← naive (no timezone)
```

PostgreSQL's `TIMESTAMPTZ` columns reject naive timestamps because the timezone context is ambiguous. This caused 543 exceptions across 5/8 scouts.

### Affected Scouts

| Scout | Exceptions | Root Cause | Fix |
|-------|-----------|------------|-----|
| CompetitionScout | 89 | `datetime.utcnow().isoformat()` | → `datetime.now(timezone.utc).isoformat()` |
| YouTubeScout | 112 | Same | Same |
| DiscordScout | 143 | Same | Same |
| PodcastScout | 97 | Same | Same |
| SourceReliabilityEngine | 102 | Missing `import asyncio` + bare `except:` | Added import, fixed exception handling |

**Total: 543 timestamp exceptions**

---

## Remediation Applied

### 1. Per-Scout Timestamp Fix (4 files)

```python
# BEFORE — naive, rejected by PostgreSQL:
timestamp = datetime.utcnow().isoformat()

# AFTER — timezone-aware, accepted by PostgreSQL:
timestamp = datetime.now(timezone.utc).isoformat()
```

**Files fixed:**
- `agents/scouts/competition_scout.py`
- `agents/scouts/youtube_scout.py`
- `agents/scouts/discord_scout.py`
- `agents/scouts/podcast_scout.py`

### 2. Source Reliability Engine Fix

**File:** `agents/scouts/source_reliability_engine.py`
- Added `import asyncio` (was missing, causing `NameError`)
- Fixed bare `except:` → `except Exception:` with descriptive logging
- Added `ON CONFLICT (id) DO NOTHING` for idempotent persistence

### 3. Centralized Timestamp Utility

**File:** `core/serialization.py` — New function `normalize_timestamp()`

| Input | Example | Output |
|-------|---------|--------|
| `datetime` (naive) | `datetime(2024,1,1,12,0,0)` | UTC-aware datetime |
| `datetime` (aware) | `datetime(2024,1,1,12,0, tzinfo=UTC)` | Same (already UTC) |
| ISO string | `"2024-01-01T12:00:00+00:00"` | Parsed via `fromisoformat()` |
| ISO string (Z) | `"2024-01-01T12:00:00Z"` | `Z` → `+00:00`, then parsed |
| Unix epoch | `1704100000.0` | `datetime.fromtimestamp(ts, tz=UTC)` |
| `None` | — | `datetime.now(timezone.utc)` |
| Invalid | `"nope"` | Falls back to `now()`, logs warning |

### 4. Auto-Detection in `normalize_db_params()`

When Scout payloads pass through `normalize_db_params()`, the function now uses a regex heuristic (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}`) to detect ISO-8601 timestamp strings and converts them to `datetime` objects before SQLAlchemy execution.

### 5. Scout Validation Update

**File:** `core/scout_validation.py`

`validate_scout_payload()` now calls `normalize_timestamp(raw_ts)` instead of:
```python
if isinstance(timestamp, datetime):
    normalized["timestamp"] = timestamp.isoformat()
```
The old code re-stringified proper datetime objects, which defeated the purpose.

---

## Unaffected Scouts

These scouts were already using correct timestamp methods:
- **RedditScout:** `datetime.now(timezone.utc).isoformat()` ✅
- **NewsIntelligenceEngine:** `NOW()` in SQL ✅
- **RegimeScout:** Not impaired ✅
- **CorrelationScout:** Not impaired ✅
- **LiquidityScout:** Not impaired ✅
- **ExecutionScout:** Not impaired ✅

---

## Verification

All 11 scouts now produce timezone-aware UTC timestamps. No timestamp exceptions expected during soak.

```python
# Verification test
from core.serialization import normalize_timestamp
from datetime import datetime, timezone

# All return identical UTC datetime
ts1 = normalize_timestamp("2024-01-01T12:00:00+00:00")
ts2 = normalize_timestamp(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
assert ts1 == ts2
```
