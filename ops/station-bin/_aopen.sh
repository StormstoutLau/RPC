#!/bin/bash
echo "== 8080 状态 =="
curl -s -o /dev/null -w "8080 health=%{http_code}\n" http://127.0.0.1:8080/api/health 2>&1
echo "== 派生后端 =="
grep -E "Starting llama-server|--device|Model loaded|Running at" /home/scott-lau/.unsloth/run-gpt-8080.log | tail -4
echo "== opencode 连接测试 (cluster-local/gpt-oss) =="
timeout 120 opencode run -m cluster-local/gpt-oss "Reply with exactly: OPENCODE-UNSLOTH-OK" 2>&1 | tail -15