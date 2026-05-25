"""
Phase 27: Safely append Phase 26 + Phase 27 methods to timescale_client.py.
Writes the method bodies to a temp file, then appends.
"""
import ast

TARGET = "data/storage/timescale_client.py"
APPENDIX = "scripts/phase27_appendix.py"

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

# Check what's present
missing = []
for name in [
    "log_scout_influence", "log_economic_attribution",
    "get_scout_influence_summary", "get_economic_attribution_summary",
    "evolutionary_garbage_collection",
]:
    if f"async def {name}" in content:
        print(f"  {name}: already present")
    else:
        missing.append(name)
        print(f"  {name}: MISSING")

if not missing:
    print("All methods present — no changes needed")
    exit(0)

# Read appendix
with open(APPENDIX, "r", encoding="utf-8") as f:
    appendix = f.read()

# Append
content = content.rstrip("\n") + "\n\n" + appendix + "\n"

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Appended missing methods: {missing}")

# Verify
try:
    ast.parse(content)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
