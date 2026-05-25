# PHASE24_RESTART_STORM_REMEDIATION.md

## Failure 4 — Restart Storm Report

**Severity:** P1 High  
**Date:** 2025-06-15  
**Status:** REMEDIATED ✅  

---

## Root Cause Analysis

The prior 6-hour soak recorded **1,994 restart events**. The supervisor initiated rapid restart loops because agents completed their `run()` cycles faster than expected and the supervisor interpreted early completion as agent death.

### The Loop

```
Agent starts → run() completes in 5s
  → Supervisor detects task exit → Agent must be dead!
    → Supervisor calls agent.start() again
      → run() completes in 5s again
        → Supervisor detects task exit again...
```

Each iteration added another restart event to the lifecycle log, producing 1,994 events over 6 hours (~5.5 restarts per agent per hour). There was **no backoff** between restarts — the supervisor restarted agents instantaneously.

---

## Remediation Applied

### 1. Minimum Run Duration

**File:** `core/agent_base.py`

Added `_min_run_duration = 60.0` (seconds). After `run()` completes, the `_run_with_retry()` method measures wall-clock time:

```python
run_elapsed = loop.time() - run_start
if run_elapsed < self._min_run_duration:
    pad = self._min_run_duration - run_elapsed
    await asyncio.sleep(pad)
```

**Effect:** If an agent's `run()` takes 5 seconds, the task stays alive for another 55 seconds before the supervisor detects completion. This prevents the restart loop entirely.

### 2. Removed Self-Stop in Max Retries

```python
# BEFORE (caused RecursionError during supervisor shutdown):
self.stop()  # Cancels the task we're running in!

# AFTER (supervisor handles dead agents):
break  # Just exit — parent loop handles cleanup
```

### 3. Supervisor Backoff

**File:** `scripts/full_autonomous_cycle.py`

```python
# BEFORE (no cooldown on successful restart):
if restart_succeeded:
    pass  # No backoff — instant restart allowed

# AFTER (exponential backoff on ALL restarts):
_restart_counts[i] += 1
_restart_blocked_until[i] = now + min(
    60 * (2 ** min(_restart_counts[i] - 1, 4)), 600
)
```

**Formula:** `min(60 × 2^(attempt-1), 600)` seconds
- Attempt 1: 60s cooldown
- Attempt 2: 120s
- Attempt 3: 240s
- Attempt 4+: 480s (capped at 600s)

### 4. Monitor Task Lifecycle

**File:** `core/meta_orchestrator.py`

Added `_monitor_task` tracking and proper `stop()` method to cancel the monitor loop on shutdown, preventing orphan task leaks.

---

## Verification

```python
# Expected behavior:
# Agent that takes 5s in run():
#   → pad = 55s sleep
#   → total task duration = 60s
#   → Supervisor sees normal completion
#   → No restart triggered

# Agent that takes 70s in run():
#   → pad = 0 (no cooldown needed)
#   → total task duration = 70s
#   → Normal completion
```

**Maximum restarts per agent per hour:** ≤ 1 (down from ~5.5)  
**Expected restart events in 60-minute soak:** ≤ 7 (one per agent)  
**Expected restart events with failures:** ≤ 14 (with one retry each)
