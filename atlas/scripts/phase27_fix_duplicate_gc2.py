"""
Phase 27A/E: Remove duplicate evolutionary_garbage_collection method.
Lines 2612-2729 is the first copy (with dry_run now implemented).
Lines 2730+ is the second copy (the original without dry_run).
Remove lines 2730 onward (second copy) to keep the fixed first copy.
"""
import re

with open('data/storage/timescale_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find the start of the second GC method (second occurrence)
occurrences = [i for i, line in enumerate(lines) if 'def evolutionary_garbage_collection' in line]
print(f'Found {len(occurrences)} occurrences at lines: {[o+1 for o in occurrences]}')

if len(occurrences) >= 2:
    # Remove from the second occurrence to end of file (or to the next class/import)
    start_remove = occurrences[1]  # 0-indexed
    
    # Find end of file
    end_remove = len(lines)
    
    # Check if there's anything after the second GC worth keeping (like a next method)
    # Look for the next class or next top-level method
    remaining = lines[start_remove:]
    next_class_or_def = None
    for i, line in enumerate(remaining):
        stripped = line.strip()
        if stripped.startswith('class ') or stripped.startswith('def '):
            next_class_or_def = start_remove + i
            break
    
    if next_class_or_def and next_class_or_def > occurrences[1] + 5:
        # There's another method/class after the second GC - keep it
        print(f'Preserving content after line {next_class_or_def + 1}')
        end_remove = next_class_or_def
    
    # Actually, let me just find what comes after the second GC
    remaining_after = '\n'.join(lines[occurrences[1]:])
    print(f'\nSecond GC starts at line {occurrences[1]+1}')
    print(f'Remaining after first GC: end of file ({end_remove} lines)')
    
    # Remove the second copy
    new_lines = lines[:occurrences[1]]
    content = '\n'.join(new_lines)
    
    print(f'Removed lines {occurrences[1]+1} to {end_remove} (second GC method)')

with open('data/storage/timescale_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
count = content.count('def evolutionary_garbage_collection')
print(f'\nAfter fix: {count} copies remaining')
if count == 1:
    print('SUCCESS: Duplicate removed!')
print(f'Total lines: {len(content.split(chr(10)))}')
