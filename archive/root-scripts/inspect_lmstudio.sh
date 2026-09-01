#!/bin/bash
# inspect_lmstudio.sh - 检查 LM Studio 的 llama.cpp 后端版本与 RPC 能力
echo "=== LM Studio runtime 目录结构 ==="
find ~/.lmstudio/runtime -maxdepth 3 -type d 2>/dev/null | head -20

echo ""
echo "=== llama.cpp 二进制版本 ==="
for b in $(find ~/.lmstudio/runtime -type f \( -name 'llama-server' -o -name 'llama-cli' \) 2>/dev/null | grep -v backends); do
  echo "--- $b"
  "$b" --version 2>&1 | head -2
done

echo ""
echo "=== RPC 后端支持检查 ==="
for b in $(find ~/.lmstudio/runtime -type f -name 'libggml-rpc.so*' 2>/dev/null); do
  echo "RPC 后端存在: $b"
done

echo ""
echo "=== Vulkan 后端位置 ==="
find ~/.lmstudio/runtime -type f -name 'libggml-vulkan.so*' 2>/dev/null | head -5

echo ""
echo "=== LM Studio 版本 ==="
ls ~/.lmstudio/ 2>/dev/null | head -10
