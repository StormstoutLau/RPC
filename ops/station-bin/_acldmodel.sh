#!/bin/bash
echo "== 方案B: claude --model 直接指定后端名 =="
timeout 120 claude --model gpt-oss-120b-MXFP4 -p "Reply with exactly the single word CLAUDE-OK" < /dev/null 2>&1 | tail -8
echo "[rc=${PIPESTATUS[0]}]"