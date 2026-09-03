#!/bin/bash
KEY=sk-unsloth-4e85200232bc3ffd9ea962c827f71329
echo "== unsloth 加载的 gpt-oss-120b 正确性 =="
timeout 90 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? one number."}],"max_tokens":60,"temperature":0}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('content=',repr(d['choices'][0]['message']['content']))" 2>&1 | head -c 150
echo
echo "== 启动参数确认 (KV q8_0 + CTX 131072) =="
ps -eo cmd | grep "[u]nsloth studio run" | grep -oE "cache-type-k [a-z0-9_]+|cache-type-v [a-z0-9_]+|-c [0-9]+" | sort -u