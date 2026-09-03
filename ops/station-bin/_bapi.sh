#!/bin/bash
KEY=sk-unsloth-f5ec3cebea66f627889ae59edd8df5e3
echo "== /v1/models =="
timeout 30 curl -s http://127.0.0.1:8080/v1/models -H "Authorization: Bearer $KEY" | python3 -c "import sys,json;print([m['id'] for m in json.load(sys.stdin)['data']])" 2>&1
echo "== /v1/chat/completions model='gpt-oss-120b-MXFP4' =="
timeout 60 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"hi"}],"max_tokens":20}' | head -c 300
echo
echo "== /v1/responses (opencode 可能用) =="
timeout 60 curl -s http://127.0.0.1:8080/v1/responses -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","input":"hi","max_output_tokens":20}' | head -c 300