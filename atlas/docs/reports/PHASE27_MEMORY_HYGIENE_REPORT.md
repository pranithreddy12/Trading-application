# PHASE 27E -- EVOLUTIONARY MEMORY HYGIENE
**Date:** 2026-05-23 20:25 UTC

---

## PROBLEM

The organism lacked evolutionary garbage collection. Stale strategies, failed mutation chains,
and fossilized branches permanently occupied search space.

## SOLUTION

`data/storage/timescale_client.py` -- `evolutionary_garbage_collection()` method:

### Cleanup Rules

| Artifact | Action | Threshold |
|----------|--------|-----------|
| `code_failed` strategies | -> status='obsolete', clear compiled_code | > 24 hours old |
| `permanently_failed` strategies | -> status='obsolete' | > 7 days old |
| `invalidated` strategies | -> status='obsolete' | > 3 days old |
| `obsolete` strategies | DELETE from strategies table | > 14 days old |
| Orphan mutation records | DELETE from mutation_record | > 7 days old |

### Design Decisions

- **Soft-delete first**: Stale strategies are first marked 'obsolete' before hard-deletion at 14 days
- **Preserves audit trail**: Event lineage and audit ledger are NOT touched
- **Dry-run support**: `dry_run=True` counts affected rows without modifying them
- **Replay-safe**: No replay records are cleaned up -- only strategy search space

## DB STATE

- Total strategies after GC: 0 (already cleaned from Phase 26H P0)
- Stale strategies removed: 23 (from earlier Phase 26H fix)
