#!/bin/bash
# assemble_v020.sh — B 站组装 /opt/llama.cpp-v0.2.0 + MANIFEST + tar
set -euo pipefail
SRC="$HOME/build/llama-v0.2.0/bin"
DEST="/opt/llama.cpp-v0.2.0"
TAR="$HOME/dist/llama-v0.2.0.tar.gz"

echo "=== [1/4] 组装 $DEST ==="
sudo rm -rf "$DEST"
sudo mkdir -p "$DEST"
sudo cp -a "$SRC"/. "$DEST"/
sudo rm -rf "$DEST"/test-*  # 测试二进制不部署
echo "   已复制 $(ls "$DEST" | wc -l) 个文件"

echo "=== [2/4] 部署 gen_manifest.sh 并生成 MANIFEST ==="
VOUT=$("$DEST/llama-cli" --version 2>&1 | head -2 || true)
VER=$(echo "$VOUT" | sed -n 's/version: \([0-9.]*\).*/\1/p' | head -1)
TOOLCHAIN=$(echo "$VOUT" | sed -n 's/built with \(.*\)/\1/p')

sudo tee "$DEST/MANIFEST" > /dev/null <<EOF
# MANIFEST — 生成于 $(date +%F) 由 assemble_v020.sh
commit       = v0.2.0 (tarball 源码, md5: 77bc882c6c4112e5c56733a8ebcdd783)
version      = ${VER:-0.2.0-dev}
build_host   = scott-lau-GTR-Pro (B站, 本机编译)
build_date   = $(date +%F)
toolchain    = ${TOOLCHAIN:-unknown}
cmake_flags  = -DGGML_VULKAN=1 -DGGML_RPC=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DCMAKE_BUILD_TYPE=Release
rpc_protocol = 待实测 (升级后 A 站日志)
[md5]
EOF
cd "$DEST" && sudo md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null | sudo tee -a "$DEST/MANIFEST" > /dev/null
sudo chmod 644 "$DEST/MANIFEST"
echo "   MANIFEST: $(grep -c '^[0-9a-f]\{32\}' "$DEST/MANIFEST") 个 MD5 条目"

echo "=== [3/4] 打 tar ==="
mkdir -p ~/dist
sudo tar -czf "$TAR" -C /opt "llama.cpp-v0.2.0"
sudo chown scott-lau:scott-lau "$TAR"
echo "   $(du -h "$TAR" | cut -f1) → $TAR"

echo "=== [4/4] 完成 ==="
echo "   下一步: scp 到 A 站 + 解压校验 + 两站切换"
