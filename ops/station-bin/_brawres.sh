#!/bin/bash
KEY=sk-unsloth-204ab16d3903e075a302a482240be8b9
echo "== 原始响应 =="
timeout 60 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"2+2?"}],"max_tokens":40,"temperature":0}' | head -c 400
echo
echo "== /health =="
timeout 20 curl -s http://127.0.0.1:8080/health 2>&1 | head -c 200
echo
echo "== /v1/models =="
timeout 20 curl -s http://127.0.0.1:8080/v1/models -H "Authorization: Bearer $KEY" 2>&1 | head -c 300