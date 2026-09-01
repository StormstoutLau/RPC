#!/bin/bash
# deploy_a_v020.sh — A 站解压 v0.2.0 + MANIFEST 校验（不切 symlink）
set -euo pipefail
TAR=/tmp/llama-v0.2.0.tar.gz
DEST=/opt/llama.cpp-v0.2.0

test -f "$TAR" || { echo "❌ tar 不存在"; exit 1; }
echo "=== [1/3] 解压 ==="
sudo rm -rf "$DEST"
sudo tar -xzf "$TAR" -C /opt/
echo "   $(ls "$DEST" | wc -l) 个文件"

echo "=== [2/3] MANIFEST MD5 校验 ==="
cd "$DEST"
sed -n '/\[md5\]/,$p' MANIFEST | tail -n +2 | md5sum -c > /tmp/md5check.log 2>&1 || { echo "❌ 校验失败:"; grep -v ': OK' /tmp/md5check.log | head -10; exit 1; }
echo "   $(grep -c ': OK' /tmp/md5check.log)/$(wc -l < /tmp/md5check.log) 全部 OK"

echo "=== [3/3] 二进制冒烟（直接路径，未切 symlink） ==="
"$DEST/llama-cli" --version 2>&1 | head -2
echo "✅ A 站 v0.2.0 就绪（symlink 仍指向 9859，待两站同步切换）"
