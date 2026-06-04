#!/usr/bin/env python3
"""
Simple monitor that polls a set of dashboard endpoints and logs timestamped results to a JSONL file.
Run for a specified duration (default 3600s) and interval (default 10s).
"""
import time
import json
import urllib.request
import urllib.error
from urllib.parse import urljoin
import sys

API_BASE = 'http://127.0.0.1:8001'
ENDPOINTS = [
    '/dashboard/api/overview',
    '/dashboard/api/scouts',
    '/dashboard/api/governance/system-health',
    '/dashboard/api/governance/deployments',
    '/dashboard/api/traces?limit=20',
    '/dashboard/api/patterns',
]

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
INTERVAL = int(sys.argv[2]) if len(sys.argv) > 2 else 10
OUTFILE = sys.argv[3] if len(sys.argv) > 3 else 'monitor_dashboard.log.jsonl'

start = time.time()
end = start + DURATION
count = 0
with open(OUTFILE, 'a', encoding='utf-8') as fh:
    while time.time() < end:
        ts = time.time()
        for ep in ENDPOINTS:
            url = urljoin(API_BASE, ep)
            record = {'ts': ts, 'endpoint': ep}
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ATLAS-Monitor/1.0'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    body = r.read()
                    record['status'] = r.getcode()
                    record['len'] = len(body)
                    # try to parse a small JSON snippet
                    try:
                        data = json.loads(body.decode('utf-8'))
                        if isinstance(data, dict):
                            record['keys'] = list(data.keys())[:10]
                    except Exception:
                        record['parse_error'] = True
            except urllib.error.HTTPError as e:
                record['status'] = e.code
                record['error'] = str(e)
            except Exception as e:
                record['status'] = 'error'
                record['error'] = str(e)
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            fh.flush()
        count += 1
        time.sleep(INTERVAL)
print(f'Done; wrote {count} rounds to {OUTFILE}')
