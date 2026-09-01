#!/bin/bash
# a4_smoke.sh — BIOS 修改后 llama.cpp API 冒烟 (B 站本地)
set -uo pipefail
resp=$(curl -s -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"Say OK"}],"max_tokens":8,"temperature":0}')
echo "$resp" | head -c 500
echo
if echo "$resp" | grep -q '"content"'; then
  echo "SMOKE_OK"
else
  echo "SMOKE_FAIL"
fi
