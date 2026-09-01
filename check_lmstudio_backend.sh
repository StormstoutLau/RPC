#!/bin/bash
# check_lmstudio_backend.sh - 检查 LM Studio 2.29.1 vulkan 后端的版本与 RPC 能力
V="$HOME/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-vulkan-avx2-2.29.1"
echo "=== 目录内容 ==="
ls "$V/" | head -25
echo ""
echo "=== llama-server 版本 ==="
"$V/llama-server" --version 2>&1 | head -3
echo ""
echo "=== RPC 后端库 ==="
ls "$V/" | grep -i rpc
echo ""
echo "=== --rpc 参数支持 ==="
"$V/llama-server" --help 2>/dev/null | grep -B1 -A2 '\-\-rpc' | head -6
echo ""
echo "=== rpc-server 二进制 ==="
ls -la "$V/rpc-server" 2>/dev/null || echo "无独立 rpc-server"
echo ""
echo "=== MD5 ==="
md5sum "$V/llama-server" "$V/libggml-vulkan.so" "$V/libggml-rpc.so" 2>/dev/null
echo ""
echo "=== 关键 so 清单 ==="
ls "$V/" | grep '\.so' | head -15
