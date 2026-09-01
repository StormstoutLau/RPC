#!/bin/bash
# a4_fix_shebang.sh — 修复 pip 安装的 entry scripts 的 CI shebang (lemonade 便携构建同款坑)
set -euo pipefail
PY=/home/scott-lau/vllm-rocm/bin/python3.14
BIN=/home/scott-lau/vllm-rocm/bin

for f in ray ray-stop ray-up; do
  if [ -f "$BIN/$f" ] && head -1 "$BIN/$f" | grep -q '^#!/.*actions-runner'; then
    sed -i "1s|.*|#!$PY|" "$BIN/$f"
    echo "fixed: $BIN/$f"
  fi
done
chmod +x "$BIN"/ray* 2>/dev/null || true

# 验证
"$BIN/ray" --version 2>&1 | head -2 || "$BIN/ray" --help 2>&1 | head -2
echo "SHEBANG_FIX_DONE"
