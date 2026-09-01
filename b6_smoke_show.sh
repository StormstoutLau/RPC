#!/bin/bash
# b6_smoke_show.sh — 打印冒烟结果 (content 截断 1200 字符)
python3 - <<'PYEOF'
import json
for line in open('/tmp/b6_smoke_qwen38flash.jsonl'):
    r = json.loads(line)
    print('='*20, r['id'], r.get('finish','?'), r.get('elapsed_s'), 's')
    c = r.get('content','')
    print(c[:1200] if c else '(EMPTY content, reasoning exhausted tokens)')
PYEOF