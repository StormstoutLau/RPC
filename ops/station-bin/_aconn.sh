#!/bin/bash
KEY=sk-unsloth-6fb378896ff67d0c306f59e935a25179
echo "===== 1) opencode ====="
timeout 150 opencode run -m cluster-local/gpt-oss "Reply with exactly the single word OPENCODE-UNSLOTH-OK" 2>&1 | tail -8
echo "[opencode rc=${PIPESTATUS[0]}]"
echo
echo "===== 2) claude code ====="
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080/v1"
export ANTHROPIC_AUTH_TOKEN="$KEY"
export ANTHROPIC_DEFAULT_SONNET_MODEL="gpt-oss-120b-MXFP4"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="gpt-oss-120b-MXFP4"
export ANTHROPIC_DEFAULT_OPUS_MODEL="gpt-oss-120b-MXFP4"
export CLAUDE_CODE_ATTRIBUTION_HEADER=0
timeout 180 claude -p "Reply with exactly the single word CLAUDE-UNSLOTH-OK" 2>&1 | tail -12
echo "[claude rc=${PIPESTATUS[0]}]"