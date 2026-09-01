#!/bin/bash
# build_v020.sh — B 站构建 llama.cpp v0.2.0 (Vulkan + RPC)
set -uo pipefail
SRC="$HOME/src/llama.cpp"
BUILD="$HOME/build/llama-v0.2.0"
LOG="/tmp/build_v020.log"

echo "=== [1/4] git clone v0.2.0 ===" | tee "$LOG"
mkdir -p ~/src
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch v0.2.0 https://github.com/ggml-org/llama.cpp "$SRC" >> "$LOG" 2>&1 || { echo "❌ clone 失败"; exit 1; }
else
  cd "$SRC" && git fetch --depth 1 origin tag v0.2.0 >> "$LOG" 2>&1 && git checkout v0.2.0 >> "$LOG" 2>&1
fi
cd "$SRC"
echo "tag: $(git describe --tags 2>/dev/null || echo v0.2.0), commit: $(git rev-parse --short HEAD)" | tee -a "$LOG"

echo "=== [2/4] cmake 配置 ===" | tee -a "$LOG"
rm -rf "$BUILD"
cmake -B "$BUILD" -S "$SRC" \
  -DGGML_VULKAN=1 \
  -DGGML_RPC=ON \
  -DGGML_CPU_ALL_VARIANTS=ON \
  -DCMAKE_BUILD_TYPE=Release >> "$LOG" 2>&1 || { echo "❌ cmake 失败"; tail -20 "$LOG"; exit 1; }

echo "=== [3/4] 编译 (-j16, 预计 10-20 分钟) ===" | tee -a "$LOG"
cmake --build "$BUILD" --config Release -j 16 >> "$LOG" 2>&1 || { echo "❌ 编译失败"; tail -30 "$LOG"; exit 1; }

echo "=== [4/4] 产物盘点 ===" | tee -a "$LOG"
ls -la "$BUILD/bin/" 2>/dev/null | head -30 | tee -a "$LOG"
echo "--- .so ---" | tee -a "$LOG"
find "$BUILD" -name '*.so*' -type f | head -25 | tee -a "$LOG"
echo "=== 构建完成: $(date) ===" | tee -a "$LOG"
