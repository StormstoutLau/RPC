#!/bin/bash
set -e
cp /home/scott-lau/.config/opencode/opencode.jsonc /home/scott-lau/.config/opencode/opencode.jsonc.bak-20260904-8080
cp /home/scott-lau/.claude/settings.json /home/scott-lau/.claude/settings.json.bak-20260904-8080
bash /home/scott-lau/_aoe8080.sh 2>&1 || echo "RUN_FAIL"
echo "== 验证 opencode =="
echo 'Reply with exactly the single word A-8080-OK' | timeout 90 opencode run -m cluster-local/gpt-oss 2>&1 | tail -3
echo "[rc=${PIPESTATUS[1]}]"