#!/bin/bash
# a4_vllm_smoke.sh — vLLM TP=2 API 冒烟 (B 站本地, 端口 8081)
set -uo pipefail
t0=$(date +%s.%N)
resp=$(curl -s -X POST http://127.0.0.1:8081/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"Say OK"}],"max_tokens":16,"temperature":0}')
t1=$(date +%s.%N)
echo "$resp" | head -c 400
echo
echo "wall_time: $(echo "$t1 $t0" | awk '{printf "%.1fs", $1-$2}')"
if echo "$resp" | grep -q '"content"'; then
  echo "VLLM_SMOKE_OK"
else
  echo "VLLM_SMOKE_FAIL"
fi
