# Phase 23 Failure Ledger

| Subsystem | Issue | Root Cause | Fix | Replay Implication | Severity |
|---|---|---|---|---|---|
| Event store | Unbounded aggregate/snapshot caches | Plain dict caches never evicted old entries | Switched to bounded ordered caches with eviction | Replay remains deterministic; cache is only an acceleration layer | High |
| Copy trading | Orphan background tasks | `create_task()` was used without ownership or cleanup | Tracked background tasks, canceled them on shutdown, stopped allocator | No duplicate task re-entry; stop/start cycles are restart-safe | High |
| L1 feature agent | Pool shutdown gap | Asyncpg pool had no graceful stop path | Added stop event and deterministic pool close | Feature cycles no longer leak connections across restarts | High |
| API middleware | Unbounded rate buckets | One bucket per key, no stale-key pruning | Added rolling-window pruning and bucket cap | Rate limiting remains deterministic and bounded | High |
| Auth service | Fire-and-forget last-used updates | Validation spawned untracked update tasks | Added tracked background-task set | Audit updates remain async but no longer leak tasks | Medium |
| Supervisor | Silent shutdown suppression | `with suppress(Exception)` hid stop failures | Replaced with explicit logging and close handling | Stop failures are visible and replayable | Medium |
| Execution gateway | False kill-switch blocks under mocks | Truthy async mock values were treated as halted state | Explicitly required real active states; hardened scout refresh against non-dict mock values | Execution path is deterministic and test-safe | High |
| Kill switch | Mock-sensitive active check | `bool(halted)` treated async mock objects as active | Explicit type checks for bool/int/str states | Active-state gating matches persisted reality | High |
| Observability | Latency sample growth | In-memory lists accumulated forever | Switched to bounded deque window | Metrics remain representative without memory drift | Medium |
| Core lifecycle | Task cancellation not awaited | BaseAgent cancel path did not join tasks | Awaited canceled tasks in `BaseAgent.stop()` | Prevents orphan tasks and shutdown races | High |

## Validation Notes
- Execution certification path passed after the kill-switch hardening.
- Copy-trading regression slice passed after lifecycle cleanup.
- Institutional replay, stress, drift, scout, and recovery tests passed in the targeted slice.

## Open Follow-Up
- A true 6h or 24h wall-clock soak still needs to be scheduled in an environment that can hold the process for that duration.
- Existing copy-trader warnings in tests stem from AsyncMock fixture behavior, not a runtime defect.