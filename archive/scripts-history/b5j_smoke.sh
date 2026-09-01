#!/bin/bash
# b5j_smoke.sh — B5j 合并模型冒烟: API 生成验证
echo "===== B5j 冒烟 @ $(date '+%F %T') ====="
R=$(curl -s --max-time 90 http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"回答: 法国首都是?"}],"max_tokens":200}')
echo "$R" | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin)
  m=d['choices'][0]['message']
  c=(m.get('content') or '').strip()
  r=(m.get('reasoning_content') or '').strip()
  print('content:  ', repr(c[:100]))
  print('reasoning:', repr(r[:60]))
  print('usage:', d.get('usage',{}).get('completion_tokens'), 'tokens')
except Exception as e:
  print('FAIL:', e); print(sys.stdin.read()[:300])
"
echo "--- GTT ---"
cat /sys/class/drm/card*/device/mem_info_gtt_used | head -1
