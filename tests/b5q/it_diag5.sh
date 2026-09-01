#!/bin/bash
# 诊断: test_sync_dir.sh 为何 FAIL — sync_dir 单步手动执行, 显式输出
B5K="$HOME/scripts/b5k_sync.sh"
TMP="$(mktemp -d)"
mkdir -p "$TMP/src/publisher/model"
printf 'X%.0s' {1..100} > "$TMP/src/publisher/model/m.gguf"
mkdir -p "$TMP/dst"
echo "--- 1. sync_dir 双参显式执行 ---"
MODEL_ROOT="$TMP/src" A_HOST=127.0.0.1 bash -c "
  source '$B5K'
  sync_dir '$TMP/src/publisher/model' '$TMP/dst/publisher/model'
" ; echo "rc=$?"
echo "--- 2. 结果落盘 ---"
find "$TMP/dst" -type f 2>&1 | head -3
echo "--- 3. 本机 sshd key 登录自测 ---"
ssh -o BatchMode=yes -o ConnectTimeout=3 127.0.0.1 'echo localhost-ssh-ok' 2>&1 | head -2
rm -rf "$TMP"
