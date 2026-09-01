#!/bin/bash
# switch_v020_A.sh — A 站: 切 symlink → 重启 RPC → 验证协议版本
set -euo pipefail
echo "=== [1/3] A 站切换 symlink → v0.2.0 ==="
sudo ln -sfn llama.cpp-v0.2.0 /opt/llama.cpp
/opt/llama.cpp/llama-cli --version 2>&1 | head -1

echo "=== [2/3] 重启 RPC server ==="
pkill -x ggml-rpc-server 2>/dev/null || true
sleep 1
bash /llama-distributed/start_rpc.sh

echo "=== [3/3] 协议版本验证（vs 9859 的 v4.0.1） ==="
sleep 2
LOG=$(ls -t ~/llama-distributed/logs/rpc_*.log | head -1)
grep "Starting RPC server" "$LOG" | tail -1 || echo "⚠️ 日志中未见协议版本行"
grep -A3 "Starting RPC server" "$LOG" | tail -4
