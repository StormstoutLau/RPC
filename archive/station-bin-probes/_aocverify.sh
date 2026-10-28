#!/bin/bash
echo "== A 站 opencode cluster-local/gpt-oss 复验 =="
echo 'Reply with exactly the single word A-RE-OK' | timeout 90 opencode run -m cluster-local/gpt-oss 2>&1 | tail -4
echo "[rc=${PIPESTATUS[1]}]"
echo "== A 站 cluster-local options =="
grep -A8 '"cluster-local"' /home/scott-lau/.config/opencode/opencode.jsonc | head -10