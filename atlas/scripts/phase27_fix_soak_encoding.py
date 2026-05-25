"""Fix Unicode characters in phase27_evolutionary_soak.py for Windows cp1252 compatibility."""
import sys

with open('scripts/phase27_evolutionary_soak.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    '\u2500': '-',        # box drawing horizontal
    '\u2014': '--',       # em dash
    '\u2705': '[PASS]',   # green check
    '\u274C': '[FAIL]',   # red cross
    '\u26A0': '[!]',      # warning sign
    '\u2713': 'ok',       # check mark
    '\u2717': 'x',        # x mark
    '\u2192': '->',       # right arrow
    '\u2190': '<-',       # left arrow
    '\u2193': 'v',        # down arrow
    '\ufe0f': '',         # variation selector
    '\u2018': "'",        # left single quote
    '\u2019': "'",        # right single quote
    '\u201c': '"',        # left double quote
    '\u201d': '"',        # right double quote
    '\u2026': '...',      # ellipsis
    '\u00b7': '*',        # middle dot
    '\u00d7': 'x',        # multiplication sign
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open('scripts/phase27_evolutionary_soak.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Unicode characters fixed.")
print(f"Total replacements: {sum(content.count(k) for k in replacements)}")

# Verify no remaining non-ASCII chars in critical areas
remaining = []
for i, c in enumerate(content):
    if ord(c) > 127:
        remaining.append((i, c))
if remaining:
    print(f"WARNING: {len(remaining)} non-ASCII chars still present:")
    for pos, c in remaining[:10]:
        print(f"  Pos {pos}: U+{ord(c):04X} {repr(c)}")
else:
    print("All non-ASCII characters removed. File is ASCII-safe.")

sys.stdout.flush()
