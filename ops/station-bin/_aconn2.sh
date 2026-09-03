#!/bin/bash
KEY=sk-unsloth-6fb378896ff67d0c306f59e935a25179
echo "== A) /v1/messages 用 Bearer =="
timeout 120 curl -s http://127.0.0.1:8080/v1/messages -H "Authorization: Bearer $KEY" -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","max_tokens":48,"messages":[{"role":"user","content":"Reply exactly ANTHROPIC-OK"}]}' 2>&1 | head -c 300
echo; echo
echo "== B) opencode（已加 key，90s） =="
timeout 90 opencode run -m cluster-local/gpt-oss "Reply with exactly the single word OPENCODE-UNSLOTH-OK" 2>&1 | tail -6
echo "[opencode rc=${PIPESTATUS[0]}]"
echo
echo "== C) claude -p（Bearer，150s） =="
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080/v1"
export ANTHROPIC_AUTH_TOKEN="$KEY"
export ANTHROPIC_DEFAULT_SONNET_MODEL="gpt-oss-120b-MXFP4"
export CLAUDE_CODE_ATTRIBUTION_HEADER=0
timeout 150 claude -p "Reply with exactly the single word CLAUDE-UNSLOTH-OK" 2>&1 | tail -8
echo "[claude rc=${PIPESTATUS[0]}]"