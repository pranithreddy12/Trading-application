"""
Restore missing methods to timescale_client.py.
The git path has atlas/ prefix.
"""
import subprocess
import re

CURRENT_PATH = 'data/storage/timescale_client.py'
GIT_PATH = 'atlas/data/storage/timescale_client.py'

# Read current file
with open(CURRENT_PATH, 'r', encoding='utf-8') as f:
    current_content = f.read()
    current_lines = current_content.split('\n')

print(f'Current file: {len(current_lines)} lines')

# Get committed file from git with correct path
result = subprocess.run(
    ['git', 'show', f'HEAD:{GIT_PATH}'],
    capture_output=True, text=True, cwd='.'
)
if result.returncode != 0:
    print(f'Error: {result.stderr}')
    # Try without atlas/ prefix
    result = subprocess.run(
        ['git', 'show', f'HEAD:{CURRENT_PATH}'],
        capture_output=True, text=True, cwd='.'
    )
    print(f'Retry stderr: {result.stderr}')

committed_content = result.stdout
committed_lines = committed_content.split('\n')
print(f'Committed file: {len(committed_lines)} lines')

# Check for missing methods in current file
missing = []
critical_methods = [
    'save_mutation_record', 'save_strategy', 'get_backtest_results',
    'get_economic_attribution_summary', 'log_portfolio', 'get_execution_log',
    'save_backtest_result', 'log_event_store', 'log_agent_lifecycle',
    'get_strategy_by_id', 'get_recent_trades', 'get_recent_patterns',
    'get_recent_strategies', 'get_recent_backtest_results',
]
for m in critical_methods:
    found = m in current_content
    if not found:
        missing.append(m)

print(f'\nMissing methods ({len(missing)}):')
for m in missing:
    print(f'  - {m}')

# Find the methods in the committed file that need to be appended
# Look for 'async def XXXX' starting after get_recent_feature_combos
# The committed file has all the methods

# Find the section to append
# In the committed file, methods after get_recent_feature_combos
idx = committed_content.find('async def get_recent_feature_combos')
if idx >= 0:
    # Find the NEXT method after get_recent_feature_combos
    after = committed_content[idx + 80:]  # skip past the current method
    # Find next method definition
    m = re.search(r'\n    async def ', after)
    if m:
        next_method_start = idx + 80 + m.start()
        # Everything from the next method to end of committed file
        append_content = committed_content[next_method_start:]
        append_lines = append_content.split('\n')
        print(f'\nContent to append: {len(append_lines)} lines')
        print(f'First 3 lines of append:')
        for line in append_lines[:3]:
            print(f'  {line}')
        print(f'Last 3 lines of append:')
        for line in append_lines[-3:]:
            print(f'  {line}')
        
        # Also add the Phase 26 methods that were uncommitted
        # Check if get_economic_attribution_summary is in the append
        if 'get_economic_attribution_summary' in append_content:
            print('\nPhase 26 methods already in committed append ✅')
        else:
            print('\nget_economic_attribution_summary NOT in committed append - Phase 26 addition was lost')
            # We need to recreate it from the git diff
            phase26_addition = """

    async def get_economic_attribution_summary(self, hours: int = 24) -> list[dict]:
        \"\"\"Fetch recent economic attribution records for trust evolution.\"\"\"
        async with self.engine.connect() as conn:
            r = await conn.execute(text(\"\"\"
                SELECT source_scout, COUNT(*) as n_strategies,
                       AVG(sharpe_contribution) as avg_sharpe,
                       AVG(pnl_contribution) as avg_pnl,
                       SUM(CASE WHEN survived_validation THEN 1 ELSE 0 END) as n_survived,
                       AVG(attribution_weight) as avg_weight
                FROM scout_economic_attribution
                WHERE created_at > NOW() - INTERVAL :hours_str
                GROUP BY source_scout
                ORDER BY avg_sharpe DESC
            \"\"\"), {"hours_str": f"{hours} hours"})
            return [
                {
                    "source_scout": row[0],
                    "n_strategies": int(row[1]),
                    "avg_sharpe_contribution": float(row[2] or 0),
                    "avg_pnl_contribution": float(row[3] or 0),
                    "n_survived_validation": int(row[4] or 0),
                    "avg_attribution_weight": float(row[5] or 0),
                }
                for row in r.fetchall()
            ]
"""
            print('Phase 26 addition will be appended separately')
        
        # Now, append the committed content to the current file
        new_content = current_content.rstrip() + '\n' + append_content
        with open(CURRENT_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        new_lines = new_content.split('\n')
        print(f'\nNew file: {len(new_lines)} lines')
        
        # Verify missing methods
        for m in missing:
            if m in new_content:
                print(f'  {m}: RESTORED ✅')
            else:
                print(f'  {m}: STILL MISSING ❌')
    else:
        print('Could not find next method after get_recent_feature_combos')
else:
    print('Could not find get_recent_feature_combos in committed file')
