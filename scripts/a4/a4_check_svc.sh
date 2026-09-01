#!/bin/bash
# a4_check_svc.sh — 检查两站 llama/rpc 服务状态 + API 冒烟
set -uo pipefail
echo "=== B站 (head) ==="
echo "llama-server: $(systemctl is-active llama-server)"
echo "=== A站 (worker) ==="
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local "echo rpc-server: \$(systemctl is-active rpc-server)"
echo "=== B站 API 冒烟 ==="
sleep 5
if curl -s http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo "LLAMA_API_OK"
else
  echo "LLAMA_API_PENDING (加载中)"
fi
echo "CHECK_DONE"
