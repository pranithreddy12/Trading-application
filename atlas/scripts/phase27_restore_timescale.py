"""
Restore the timescale_client.py file that had methods deleted by the duplicate GC removal.

Strategy:
1. Read current file (has Phase 27 changes to get_recent_feature_combos and GC method)
2. Check what's missing by comparing with git committed version
3. Append missing committed methods from git
4. Append Phase 26 uncommitted methods (from the conversation-start git diff)
"""
import subprocess
import re

CURRENT_PATH = 'data/storage/timescale_client.py'

# Read current file
with open(CURRENT_PATH, 'r', encoding='utf-8') as f:
    current_content = f.read()
    current_lines = current_content.split('\n')

print(f'Current file: {len(current_lines)} lines')

# Get committed file from git
result = subprocess.run(
    ['git', 'show', f'HEAD:{CURRENT_PATH}'],
    capture_output=True, text=True, cwd='.'
)
committed_content = result.stdout
committed_lines = committed_content.split('\n')
print(f'Committed file: {len(committed_lines)} lines')

# Find where the current file's last method (before GC) ends
# The last async method before GC is at line 2612
# Let's find what's between the last original method and the GC method
# The get_recent_feature_combos method ends at the 'return combos' line
return_combos_idx = current_content.rfind('return combos')
if return_combos_idx >= 0:
    # Content from return combos onward includes the GC method
    end_of_original = current_content[:return_combos_idx + len('return combos')]
    end_lines = end_of_original.split('\n')
    print(f'Last original content ends around line {len(end_lines)}')

# Find the boundary: what was the LAST committed method that's present?
# The get_recent_feature_combos method is at line 2563 in both committed and current
# After it, there should be more methods in the committed file

# Let's find get_recent_feature_combos in committed file and see what comes after
committed_idx = committed_content.find('async def get_recent_feature_combos')
if committed_idx >= 0:
    after_combos = committed_content[committed_idx:]
    # Find the next method after get_recent_feature_combos
    next_method_match = re.search(r'\n    async def ', after_combos[50:])  # skip past the current method
    if next_method_match:
        next_method_start = committed_idx + 50 + next_method_match.start() + 1
        # Everything from next method onward is what should be preserved
        committed_after = committed_content[next_method_start:]
        print(f'Committed methods after get_recent_feature_combos: {len(committed_after.split(chr(10)))} lines')
        
        # Check what's currently at the end of the file
        current_end = current_lines[len(current_lines)-3:] if len(current_lines) >= 3 else current_lines
        print(f'Current file ends with: {current_end}')

# Now let's check which Phase 26 methods exist and which are missing
# Phase 26 added:
phase26_methods = [
    'log_scout_influence',
    'log_economic_attribution', 
    'get_scout_influence_summary',
    'get_economic_attribution_summary',
]

for m in phase26_methods:
    found = m in current_content
    print(f'  Phase 26 {m}: {"PRESENT" if found else "MISSING"}')

# Check for save_mutation_record and other critical methods
critical = ['save_mutation_record', 'save_strategy', 'get_backtest_results']
for m in critical:
    found = m in current_content
    print(f'  Critical {m}: {"PRESENT" if found else "MISSING"}')
