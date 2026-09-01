#!/bin/bash
# fix_runpath_v2.sh — 修复 v0.2.0 全部 ELF（含 -impl.so 库）的 RUNPATH → $ORIGIN
set -euo pipefail
DEST=/opt/llama.cpp-v0.2.0
command -v patchelf >/dev/null || { sudo apt-get install -y patchelf >/dev/null 2>&1; }

echo "=== 修复全部 ELF RUNPATH ==="
cd "$DEST"
COUNT=0
for f in llama-* ggml-rpc-server libllama*.so* libggml*.so* libmtmd.so*; do
  [ -f "$f" ] || continue
  # 跳过符号链接（指向实体文件，实体会被处理）
  [ -L "$f" ] && continue
  file "$f" 2>/dev/null | grep -q ELF || continue
  sudo patchelf --set-rpath '$ORIGIN' "$f"
  COUNT=$((COUNT+1))
done
echo "   已修复 $COUNT 个 ELF"

echo "=== 验证（含依赖链） ==="
readelf -d ./llama-cli | grep -i runpath
readelf -d ./libllama-cli-impl.so | grep -i runpath
ldd ./llama-cli 2>&1 | grep -c 'not found' || true
./llama-cli --version 2>&1 | head -1

echo "=== 重新生成 MANIFEST md5 节 + tar ==="
sudo bash -c "cd $DEST && awk '/\[md5\]/{exit}1' MANIFEST > /tmp/mf_h && cat /tmp/mf_h > MANIFEST && echo '[md5]' >> MANIFEST && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null >> MANIFEST && chmod 644 MANIFEST"
echo "   MANIFEST: $(grep -c '^[0-9a-f]\{32\}' MANIFEST) 条"
sudo tar -czf ~/dist/llama-v0.2.0.tar.gz -C /opt llama.cpp-v0.2.0
sudo chown scott-lau:scott-lau ~/dist/llama-v0.2.0.tar.gz
echo "   新 tar md5: $(md5sum ~/dist/llama-v0.2.0.tar.gz | cut -d' ' -f1)"
