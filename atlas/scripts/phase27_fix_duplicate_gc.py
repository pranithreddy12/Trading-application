"""
Phase 27A/E: Fix duplicate evolutionary_garbage_collection in timescale_client.py.
The fix script ran twice, leaving two copies of the method. Remove the first duplicate
and fix the dry_run parameter to actually be respected.
"""
import re

with open('data/storage/timescale_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences
count = content.count('async def evolutionary_garbage_collection')
print(f'Found {count} copies of evolutionary_garbage_collection')

if count >= 2:
    # Find the range to remove: from the first header block to just before the second method
    first_idx = content.find('# ================================================================\n    # PHASE 27 — EVOLUTIONARY MEMORY HYGIENE\n    # ================================================================\n\n\n    # ================================================================\n    # PHASE 27 — EVOLUTIONARY MEMORY HYGIENE\n    # ================================================================\n\n    async def evolutionary_garbage_collection')
    
    if first_idx >= 0:
        # Find the end of this first method (second occurrence starts after)
        second_start = content.find(
            '\n\n    async def evolutionary_garbage_collection',
            first_idx + 100
        )
        if second_start >= 0:
            # Remove from first_idx to second_start (the blank line before the second def)
            content = content[:first_idx] + '\n\n' + content[second_start+2:]
            print(f'Removed duplicate GC method (lines {first_idx}-{second_start})')
        else:
            print('ERROR: Could not find second GC method')
    else:
        print('ERROR: Could not find first header')
    
    # Now check if it's still duplicated
    count = content.count('async def evolutionary_garbage_collection')
    print(f'After fix: {count} copies remaining')

# Now fix the dry_run parameter to actually be respected
old_dry_run = '''    async def evolutionary_garbage_collection(self, dry_run: bool = True) -> dict:
        """Phase 27E: Clean up stale evolutionary artifacts.
        
        Marks and/or removes:
        - code_failed strategies older than 24 hours (failed code compilation)
        - permanently_failed strategies older than 7 days
        - invalidated strategies older than 3 days
        - obsoletes strategies that are > 7 days old with no backtest results
        
        Preserves audit trail and event lineage.
        Returns dict of counts of affected rows per table.
        """
        from loguru import logger
        results = {}
        try:
            async with self.engine.begin() as conn:'''

new_dry_run = '''    async def evolutionary_garbage_collection(self, dry_run: bool = True) -> dict:
        """Phase 27E: Clean up stale evolutionary artifacts.
        
        Marks and/or removes:
        - code_failed strategies older than 24 hours (failed code compilation)
        - permanently_failed strategies older than 7 days
        - invalidated strategies older than 3 days
        - obsoletes strategies that are > 7 days old with no backtest results
        
        Preserves audit trail and event lineage.
        Returns dict of counts of affected rows per table.
        If dry_run=True, only counts rows that WOULD be affected without modifying them.
        """
        from loguru import logger
        results = {"dry_run": dry_run}
        try:
            async with self.engine.begin() as conn:
                if dry_run:
                    logger.info("evolutionary_gc: DRY RUN — no actual changes made")
                    # Count but don't modify
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM strategies
                        WHERE status = 'code_failed'
                          AND created_at < NOW() - INTERVAL '24 hours'
                    """))
                    results["code_failed_obsoleted"] = r.fetchone()[0]
                    
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM strategies
                        WHERE status = 'permanently_failed'
                          AND created_at < NOW() - INTERVAL '7 days'
                    """))
                    results["perm_failed_obsoleted"] = r.fetchone()[0]
                    
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM strategies
                        WHERE status = 'invalidated'
                          AND created_at < NOW() - INTERVAL '3 days'
                    """))
                    results["invalidated_obsoleted"] = r.fetchone()[0]
                    
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM strategies
                        WHERE status = 'obsolete'
                          AND created_at < NOW() - INTERVAL '14 days'
                    """))
                    results["obsolete_deleted"] = r.fetchone()[0]
                    
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM mutation_record
                        WHERE child_id NOT IN (SELECT id::text FROM strategies)
                          AND created_at < NOW() - INTERVAL '7 days'
                    """))
                    results["orphan_mutations_deleted"] = r.fetchone()[0]
                    
                    logger.info(f"evolutionary_gc (dry_run): code_failed->obsolete={results.get('code_failed_obsoleted',0)}, "
                                f"perm_failed->obsolete={results.get('perm_failed_obsoleted',0)}, "
                                f"invalidated->obsolete={results.get('invalidated_obsoleted',0)}, "
                                f"obsolete_deleted={results.get('obsolete_deleted',0)}")
                    return results
                
                # ==== ACTUAL EXECUTION ===='''

if old_dry_run in content:
    content = content.replace(old_dry_run, new_dry_run)
    print('OK: dry_run parameter now implemented')
else:
    print('WARN: Could not find old dry_run pattern for replacement')

with open('data/storage/timescale_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
