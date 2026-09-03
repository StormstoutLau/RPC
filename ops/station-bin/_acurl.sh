#!/bin/bash
KEY=sk-unsloth-60153365833b5b5fa37954a69ddd4c07
echo "== 直接 curl 8080 OpenAI chat (非流) =="
timeout 150 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"Reply with exactly: CURL-UNSLOTH-OK"}],"max_tokens":40,"temperature":0}' 2>&1 | head -c 500
echo
echo "== /v1/models =="
curl -s http://127.0.0.1:8080/v1/models -H "Authorization: Bearer $KEY" 2>&1 | head -c 300