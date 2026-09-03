#!/bin/bash
KEY=sk-unsloth-204ab16d3903e075a302a482240be8b9
echo "== B 站 gpt-oss-120b (infer-load unsloth) 正确性 =="
timeout 60 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? one number."}],"max_tokens":40,"temperature":0}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('content=',repr(d['choices'][0]['message']['content']))" 2>&1 | head -c 120