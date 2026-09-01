#!/bin/bash
# api_test.sh - B 站本机 API 冒烟测试
curl -s --max-time 300 http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "minimax", "messages": [{"role": "user", "content": "Reply with exactly: API_PONG. No thinking."}], "max_tokens": 1024}' \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=d['choices'][0]['message']
print('content:', repr(m.get('content','')[:300]))
print('reasoning:', repr((m.get('reasoning_content') or '')[:300]))
print('finish:', d['choices'][0].get('finish_reason'))
print('用量:', d['usage'])
"
