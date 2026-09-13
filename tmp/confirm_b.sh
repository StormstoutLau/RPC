#!/bin/bash
echo "=== B 站 clone 结果 ==="
if [ -d /tmp/hermes_agent_b ]; then
  du -sh /tmp/hermes_agent_b
  echo "B 站 clone 成功"
else
  echo "B 站无 clone 结果"
fi
echo ""
echo "=== Nemotron 已完成题目完整度 ==="
python3 - <<'PY'
import json, glob
for f in sorted(glob.glob('/tmp/res_nem120b/*.jsonl')):
    r=json.load(open(f,encoding='utf-8'))
    a=r.get('answer') or ''
    u=r.get('usage') or {}
    fl='OK' if len(a.split())>40 else 'EMPTY'
    print('{} [{}] ans={}tok comp={} el={}s'.format(r['id'],fl,len(a.split()),u.get('completion_tokens'),r.get('elapsed')))
PY