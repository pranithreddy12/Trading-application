import re
from collections import Counter, defaultdict

LOG = 'scripts/logs/phase37_soak_30m.log'
pattern = re.compile(r"UUID normalization: (.*?) in (.*?)(?: ->|$)")

counts = Counter()
by_type = Counter()
examples = defaultdict(list)

with open(LOG, 'r', encoding='utf-8') as f:
    for line in f:
        m = pattern.search(line)
        if m:
            typ = m.group(1).strip()
            fn = m.group(2).strip()
            counts[fn] += 1
            by_type[typ] += 1
            if len(examples[fn]) < 3:
                examples[fn].append(line.strip())

print('UUID normalization summary for', LOG)
print('Total unique call sites:', len(counts))
print('\nTop call sites:')
for fn, c in counts.most_common(20):
    print(f'  {c:4d}  {fn}')

print('\nBy warning type:')
for typ, c in by_type.most_common():
    print(f'  {c:4d}  {typ}')

print('\nExamples (up to 3 per call site):')
for fn, ex in list(examples.items())[:10]:
    print('\n--', fn)
    for e in ex:
        print('   ', e)
