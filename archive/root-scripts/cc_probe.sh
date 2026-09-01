#!/bin/bash
# 排查: claude→litellm→llama.cpp 链路断点定位
set -u
exec 2>&1
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')

echo "=== 1. litellm /v1/messages (anthropic 格式) 直测 ==="
curl -s -w "\nHTTP=%{http_code}\n" http://127.0.0.1:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"nemotron","max_tokens":64,"messages":[{"role":"user","content":"Reply exactly: PONG"}]}' | head -c 500

echo ""
echo "=== 2. OpenAI /v1/chat/completions (对照组, 已知可用) ==="
curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://127.0.0.1:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"nemotron","max_tokens":64,"messages":[{"role":"user","content":"hi"}]}'

echo "=== 3. litellm journal 最近错误 ==="
sudo journalctl -u litellm --since '-10 min' --no-pager 2>/dev/null | grep -iE 'error|404|500' | tail -5 || echo "(无)"
echo DONE_PROBE
