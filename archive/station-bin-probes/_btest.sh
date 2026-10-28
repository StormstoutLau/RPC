#!/bin/bash
echo "=== B claude 现状测试 ==="
timeout 100 claude -p "Reply with exactly the single word B-CLAUDE-OK" < /dev/null 2>&1 | tail -6
echo "[rc=${PIPESTATUS[0]}]"
echo
echo "=== B opencode cluster-litellm/nemotron ==="
echo 'Reply with exactly the single word B-OPENCODE-OK' | timeout 100 opencode run -m cluster-litellm/nemotron 2>&1 | tail -4
echo "[rc=${PIPESTATUS[1]}]"