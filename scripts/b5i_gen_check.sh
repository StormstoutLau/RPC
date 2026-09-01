#!/bin/bash
# b5i_gen_check.sh — 生成内容验证 (content vs reasoning_content)
curl -s --max-time 90 http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"直接回答不要思考: 1+1=?"}],"max_tokens":50}' \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=d['choices'][0]['message']
print('content:  ', repr((m.get('content') or '')[:80]))
print('reasoning:', repr((m.get('reasoning_content') or '')[:80]))
"
