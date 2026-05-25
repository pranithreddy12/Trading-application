"""
Fix the syntax error in evolutionary_garbage_collection logger.info call.
The `""` implicit concatenation inside f-strings causes a syntax error on Windows/Python 3.11.
"""
import re

with open('data/storage/timescale_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the problematic section
old = """                logger.info(
                    f\"evolutionary_gc: code_failed->obsolete={results.get('code_failed_obsoleted',0)}, \"\"
                    f\"perm_failed->obsolete={results.get('perm_failed_obsoleted',0)}, \"\"
                    f\"invalidated->obsolete={results.get('invalidated_obsoleted',0)}, \"\"
                    f\"obsolete_deleted={results.get('obsolete_deleted',0)}\"
                )"""

new = """                logger.info(
                    \"evolutionary_gc: code_failed->obsolete=%s, \"
                    \"perm_failed->obsolete=%s, \"
                    \"invalidated->obsolete=%s, \"
                    \"obsolete_deleted=%s\",
                    results.get('code_failed_obsoleted', 0),
                    results.get('perm_failed_obsoleted', 0),
                    results.get('invalidated_obsoleted', 0),
                    results.get('obsolete_deleted', 0)
                )"""

if old in content:
    content = content.replace(old, new)
    print("Fixed logger.info call")
else:
    # Try alternative pattern
    print("WARN: Could not find exact pattern. Searching...")
    idx = content.find("evolutionary_gc: code_failed->obsolete=")
    if idx >= 0:
        print(f"Found at position {idx}")
        print(content[idx-50:idx+300])
    else:
        print("Pattern not found at all")

with open('data/storage/timescale_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify syntax
import ast
try:
    ast.parse(open('data/storage/timescale_client.py').read())
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    # Show context around the error
    lines = open('data/storage/timescale_client.py').readlines()
    if e.lineno:
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            print(f"  {i+1}: {lines[i].rstrip()}")
