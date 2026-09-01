#!/bin/bash
# 复测: 模型加载状态下 claude→litellm(/v1/messages)→nemotron 全链路
set -u
exec 2>&1
export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')

load-mem-gate 80 || exit 1
infer-load nvidia-nemotron-3-super 2>&1 | tail -1

echo "=== 1. litellm /v1/messages (anthropic 格式) — 模型已加载 ==="
curl -s -w "\nHTTP=%{http_code}\n" http://127.0.0.1:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"nemotron","max_tokens":64,"messages":[{"role":"user","content":"Reply exactly: PONG"}]}' | head -c 400

echo ""
echo "=== 2. claude code headless 完整测试 ==="
cd /tmp && rm -rf cc_test2 && mkdir cc_test2 && cd cc_test2
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export ANTHROPIC_AUTH_TOKEN="$KEY"
export CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1
timeout 180 claude -p "Reply with exactly: PONG" --model nemotron 2>&1 | tail -6
echo "exit=$?"

infer-unload 2>&1 | tail -1
echo DONE_CC_TEST2
