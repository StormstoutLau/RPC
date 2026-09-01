#!/bin/bash
# build_v020_local.sh — B 站从本地源码编译 llama.cpp v0.2.0 (Vulkan + RPC + CPU 变体)
set -uo pipefail
SRC="$HOME/src/llama.cpp-0.2.0"
BUILD="$HOME/build/llama-v0.2.0"
LOG="/tmp/build_v020.log"

test -d "$SRC" || { echo "❌ 源码目录不存在: $SRC"; exit 1; }

echo "=== [1/3] cmake 配置 ($(date +%T)) ===" | tee "$LOG"
rm -rf "$BUILD"
cmake -B "$BUILD" -S "$SRC" \
  -DGGML_VULKAN=1 \
  -DGGML_RPC=ON \
  -DGGML_BACKEND_DL=ON \
  -DGGML_CPU_ALL_VARIANTS=ON \
  -DCMAKE_BUILD_TYPE=Release >> "$LOG" 2>&1 || { echo "❌ cmake 失败"; tail -25 "$LOG"; exit 1; }
echo "cmake OK" | tee -a "$LOG"

echo "=== [2/3] 编译 -j16 ($(date +%T), 预计 10-25 分钟) ===" | tee -a "$LOG"
cmake --build "$BUILD" --config Release -j 16 >> "$LOG" 2>&1 || { echo "❌ 编译失败"; tail -30 "$LOG"; exit 1; }
echo "build OK" | tee -a "$LOG"

echo "=== [3/3] 产物盘点 ($(date +%T)) ===" | tee -a "$LOG"
echo "--- bin/ ---" | tee -a "$LOG"
ls "$BUILD/bin/" 2>/dev/null | tee -a "$LOG"
echo "--- .so ---" | tee -a "$LOG"
find "$BUILD" -name '*.so*' -type f -printf '%p\n' 2>/dev/null | tee -a "$LOG"
echo "=== 构建完成: $(date +%T) ===" | tee -a "$LOG"
