#!/bin/bash
echo "== B opencode cluster-local 最小消息 =="
echo 'hi' | timeout 90 opencode run -m cluster-local/gpt-oss --log-level ERROR 2>&1 | tail -8
echo "[rc=${PIPESTATUS[1]}]"
echo
echo "== 查 unsloth log 最近错误 =="
tail -30 /home/scott-lau/.unsloth/run-gpt-bkvq.log | grep -iE "error|error|400|500|fail" | tail -10