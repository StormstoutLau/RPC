#!/bin/bash
# fix_runpath.sh — 修复 v0.2.0 二进制 RUNPATH → $ORIGIN（B 站执行后重新打 tar 分发）
set -euo pipefail
DEST=/opt/llama.cpp-v0.2.0
command -v patchelf >/dev/null || { echo "安装 patchelf..."; sudo apt-get install -y patchelf >/dev/null 2>&1 || { echo "❌ patchelf 安装失败"; exit 1; }; }

echo "=== 修复 RUNPATH → \$ORIGIN ==="
cd "$DEST"
COUNT=0
for f in llama-* ggml-rpc-server; do
  [ -f "$f" ] || continue
  sudo patchelf --set-rpath '$ORIGIN' "$f"
  COUNT=$((COUNT+1))
done
echo "   已修复 $COUNT 个 ELF 二进制"

echo "=== 验证 ==="
readelf -d ./llama-cli | grep -i runpath
./llama-cli --version 2>&1 | head -1 || { echo "❌ 修复后仍失败"; exit 1; }
./llama-server --version 2>&1 | head -1 || true
./ggml-rpc-server --help 2>&1 | head -1 || true
echo "✅ RUNPATH 修复完成"

echo "=== 更新 MANIFEST 并重新打 tar ==="
sudo sed -i 's|cmake_flags  = .*|cmake_flags  = -DGGML_VULKAN=1 -DGGML_RPC=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DCMAKE_BUILD_TYPE=Release (RUNPATH patched: $ORIGIN)|' MANIFEST
sudo md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null | sudo tee -a /dev/null > /dev/null || true
# 重新生成 md5 节（patchelf 改变了二进制）
sudo bash -c 'cd '"$DEST"' && head -n "/[md5]/q" MANIFEST' 2>/dev/null || true
sudo bash -c "cd $DEST && awk '/\[md5\]/{exit}1' MANIFEST > /tmp/mf_head && sed -i 's/^# MANIFEST.*$/# MANIFEST — 重新生成于 \$(date +%F) (RUNPATH 修复后)/' /tmp/mf_head && cat /tmp/mf_head > MANIFEST && echo '[md5]' >> MANIFEST && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null >> MANIFEST"
sudo chmod 644 MANIFEST
echo "   MANIFEST: $(grep -c '^[0-9a-f]\{32\}' MANIFEST) 条"

sudo tar -czf ~/dist/llama-v0.2.0.tar.gz -C /opt llama.cpp-v0.2.0
sudo chown scott-lau:scott-lau ~/dist/llama-v0.2.0.tar.gz
echo "   新 tar: $(du -h ~/dist/llama-v0.2.0.tar.gz | cut -f1) (md5: $(md5sum ~/dist/llama-v0.2.0.tar.gz | cut -d' ' -f1))"
