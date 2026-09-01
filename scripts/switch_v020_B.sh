#!/bin/bash
# switch_v020_B.sh — B 站: 切 symlink + 验证
set -euo pipefail
echo "=== [1/2] B 站切换 symlink → v0.2.0 ==="
sudo ln -sfn llama.cpp-v0.2.0 /opt/llama.cpp
/opt/llama.cpp/llama-cli --version 2>&1 | head -1
echo "readlink: $(readlink /opt/llama.cpp)"

echo "=== [2/2] RPC 连通验证（B→A） ==="
nc -z 10.10.10.1 50052 && echo "✅ A 站 RPC 端口可达"
echo ""
echo "✅ B 站切换完成，准备跑冒烟 bench"
