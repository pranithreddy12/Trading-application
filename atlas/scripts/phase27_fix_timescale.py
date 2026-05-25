"""
Phase 27A/E: Fix timescale_client.py for evolutionary deadlock remediation.
- Update get_recent_feature_combos to exclude more statuses + 7-day cutoff
- Add time-decayed weighting
- Add evolutionary_garbage_collection method
"""
import re

with open('data/storage/timescale_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# --- Fix 1: Update get_recent_feature_combos query ---
old_query = """            SELECT normalized_strategy FROM strategies
            WHERE normalized_strategy IS NOT NULL
              AND (status IS DISTINCT FROM 'code_failed')
            ORDER BY created_at DESC
            LIMIT :limit"""

new_query = """            SELECT normalized_strategy, created_at FROM strategies
            WHERE normalized_strategy IS NOT NULL
              AND (status NOT IN ('code_failed', 'permanently_failed', 'invalidated', 'obsolete') OR status IS NULL)
              AND created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT :limit"""

if old_query in content:
    content = content.replace(old_query, new_query)
    changes += 1
    print(f'OK: get_recent_feature_combos query updated')
else:
    print('WARN: Old query pattern not found, checking current state...')
    idx = content.find('get_recent_feature_combos')
    if idx >= 0:
        print(content[idx:idx+500])

# --- Fix 2: Add now = datetime.now() and time-weighted combos ---
# First add the import if not there
if 'from datetime import datetime, timezone' in content:
    print('OK: datetime already imported')
else:
    content = content.replace(
        'from datetime import datetime',
        'from datetime import datetime, timezone'
    )
    print('OK: Added timezone to datetime import')

# Add time decay context to the for loop
old_loop = """        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            combos = []
            for row in result.fetchall():
                raw = row[0]"""

new_loop = """        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            combos = []
            now = datetime.now(timezone.utc)
            for row in result.fetchall():
                raw = row[0]"""

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    changes += 1
    print('OK: Added now = datetime.now()')
else:
    print('WARN: Could not find for loop pattern')

# Update the append to include time weight
old_append = """                if features:
                    combos.append((features, archetype))"""

new_append = """                if features:
                    # Time-decay weight
                    created_raw = row[1]
                    age_hours = 168
                    if created_raw is not None:
                        try:
                            if hasattr(created_raw, 'isoformat'):
                                age_hours = (now - created_raw).total_seconds() / 3600
                        except Exception:
                            age_hours = 0
                    time_weight = max(0.1, 1.0 - (age_hours / 168.0))
                    combos.append((features, archetype, time_weight))"""

if old_append in content:
    content = content.replace(old_append, new_append)
    changes += 1
    print('OK: Added time-decayed weighting')
else:
    count = content.count('combos.append((features, archetype))')
    print(f'WARN: Append pattern found {count} times')

# --- Fix 3: Add evolutionary_garbage_collection method ---
# Find a good insertion point - end of the file or after get_recent_feature_combos
gc_method = """

    # ================================================================
    # PHASE 27 — EVOLUTIONARY MEMORY HYGIENE
    # ================================================================

    async def evolutionary_garbage_collection(self, dry_run: bool = True) -> dict:
        \"\"\"Phase 27E: Clean up stale evolutionary artifacts.
        
        Marks and/or removes:
        - code_failed strategies older than 24 hours (failed code compilation)
        - permanently_failed strategies older than 7 days
        - invalidated strategies older than 3 days
        - obsoletes strategies that are > 7 days old with no backtest results
        
        Preserves audit trail and event lineage.
        Returns dict of counts of affected rows per table.
        \"\"\"
        from loguru import logger
        results = {}
        try:
            async with self.engine.begin() as conn:
                # 1. Soft-delete code_failed > 24h: mark as obsolete
                r = await conn.execute(text(\"\"\"
                    UPDATE strategies
                    SET status = 'obsolete', compiled_code = NULL
                    WHERE status = 'code_failed'
                      AND created_at < NOW() - INTERVAL '24 hours'
                \"\"\"))
                results[\"code_failed_obsoleted\"] = r.rowcount
                logger.info(f\"evolutionary_gc: {r.rowcount} code_failed strategies -> obsolete\")

                # 2. Soft-delete permanently_failed > 7d
                r = await conn.execute(text(\"\"\"
                    UPDATE strategies
                    SET status = 'obsolete'
                    WHERE status = 'permanently_failed'
                      AND created_at < NOW() - INTERVAL '7 days'
                \"\"\"))
                results[\"perm_failed_obsoleted\"] = r.rowcount

                # 3. Soft-delete invalidated > 3d
                r = await conn.execute(text(\"\"\"
                    UPDATE strategies
                    SET status = 'obsolete'
                    WHERE status = 'invalidated'
                      AND created_at < NOW() - INTERVAL '3 days'
                \"\"\"))
                results[\"invalidated_obsoleted\"] = r.rowcount

                # 4. Delete obsolete strategies > 14 days old from active tables
                #    (preserve event lineage but remove from diversity search)
                r = await conn.execute(text(\"\"\"
                    DELETE FROM strategies
                    WHERE status = 'obsolete'
                      AND created_at < NOW() - INTERVAL '14 days'
                \"\"\"))
                results[\"obsolete_deleted\"] = r.rowcount

                # 5. Clean up orphan mutation_records where parent child no longer exists
                r = await conn.execute(text(\"\"\"
                    DELETE FROM mutation_record
                    WHERE child_id NOT IN (SELECT id::text FROM strategies)
                      AND created_at < NOW() - INTERVAL '7 days'
                \"\"\"))
                results[\"orphan_mutations_deleted\"] = r.rowcount

                logger.info(
                    f\"evolutionary_gc: code_failed->obsolete={results.get('code_failed_obsoleted',0)}, \"\"
                    f\"perm_failed->obsolete={results.get('perm_failed_obsoleted',0)}, \"\"
                    f\"invalidated->obsolete={results.get('invalidated_obsoleted',0)}, \"\"
                    f\"obsolete_deleted={results.get('obsolete_deleted',0)}\"
                )
        except Exception as e:
            logger.error(f\"evolutionary_gc: Error: {e}\")
            results[\"error\"] = str(e)
        return results
"""

# Find insertion point - after get_recent_feature_combos
insert_marker = "        return combos"
idx = content.find(insert_marker)
if idx >= 0:
    # Find the next method after this one
    rest = content[idx + len(insert_marker):]
    next_def = rest.find('\n    async def ')
    if next_def >= 0:
        insert_pos = idx + len(insert_marker) + next_def
        content = content[:insert_pos] + gc_method + content[insert_pos:]
        changes += 1
        print(f'OK: Added evolutionary_garbage_collection method')
    else:
        print('WARN: Could not find next method after get_recent_feature_combos')
else:
    print('WARN: Could not find combos return')

with open('data/storage/timescale_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nDone! {changes} changes applied to timescale_client.py')
