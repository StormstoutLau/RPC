#!/bin/bash
KEY=sk-unsloth-3ea8ee000acbc1db06dcce310125d691
echo "== A 站 gpt-oss (infer-load unsloth) 正确性 =="
timeout 90 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? one number."}],"max_tokens":60,"temperature":0}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('content=',repr(d['choices'][0]['message']['content']))" 2>&1 | head -c 150
echo
echo "== 参数 =="
ps -eo cmd | grep "[u]nsloth studio run" | grep -oE "cache-type-k [a-z0-9_]+|-c [0-9]+" | sort -u | head