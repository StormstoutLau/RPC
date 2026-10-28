#!/bin/bash
# 验证 A 站 CLI 新端点 (8087) 实际可用
echo "== 1) opencode cluster-local/gpt-oss =="
timeout 150 opencode run -m cluster-local/gpt-oss "Reply with exactly the word OPENCODE-OK" 2>&1 | tail -6
echo "[rc=${PIPESTATUS[0]}]"
echo
echo "== 2) claude (BASE_URL 8087) =="
timeout 120 claude -p "Reply with exactly the word CLAUDE-OK" 2>&1 | tail -6
echo "[rc=${PIPESTATUS[0]}]"