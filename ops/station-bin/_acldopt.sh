#!/bin/bash
echo "== 方案A: ANTHROPIC_CUSTOM_MODEL_OPTION =="
env -u ANTHROPIC_MODEL \
  ANTHROPIC_CUSTOM_MODEL_OPTION="gpt-oss-120b-MXFP4" \
  timeout 120 claude -p "Reply with exactly the single word CLAUDE-OK" < /dev/null 2>&1 | tail -8
echo "[rc=${PIPESTATUS[0]}]"