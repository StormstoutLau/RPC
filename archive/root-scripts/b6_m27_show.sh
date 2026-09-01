#!/bin/bash
# b6_m27_show.sh — 打印 m27 冒烟结果
python3 - <<'PYEOF'
import json
for line in open('/tmp/b6_smoke_m27.jsonl'):
    r = json.loads(line)
    print('='*20, r['id'], r.get('finish','?'), r.get('elapsed_s'), 's', 'nothink' if r.get('no_think') else '')
    c = r.get('content','')
    print(c[:900] if c else '(EMPTY)')
PYEOF