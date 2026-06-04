from pathlib import Path
import json

gdir = Path(__file__).resolve().parent.parent / 'atlas' / 'governance'
files = sorted(gdir.glob('governance_analytics_*.json'))
if not files:
    print('No analytics files found')
    raise SystemExit(1)

latest = files[-1]
prev = files[-2] if len(files) > 1 else None

def load(path):
    return json.loads(Path(path).read_text())

latest_data = load(latest)
prev_data = load(prev) if prev else None

def delta(k):
    if not prev_data:
        return None
    a = latest_data.get(k, 0)
    b = prev_data.get(k, 0)
    try:
        return a - b
    except Exception:
        return None

print('Latest analytics file:', latest.name)
if prev:
    print('Previous analytics file:', prev.name)

for m in ['governance_coverage_percent','repair_dependency_percent','bypass_rate_percent']:
    print(m + ':', latest_data.get(m), 'delta:', delta(m))

print('\nTop violation signatures (latest):')
for s in latest_data.get('violation_signatures', [])[:10]:
    print(s)

print('\nRepair hotspots (latest):')
print(latest_data.get('repair_hotspots', {}))

raise SystemExit(0)
