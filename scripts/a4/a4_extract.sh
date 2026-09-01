#!/bin/bash
# a4_extract.sh — 两站: 解压 vllm-rocm 便携构建 (part01+02 是同一 tar 的分卷, 顶层 ./ 摊平)
# 用法: bash a4_extract.sh  (各站本地运行)
set -euo pipefail
DIST=/home/scott-lau/vllm-dist
DEST=/home/scott-lau/vllm-rocm
mkdir -p "$DEST"

PY=$(ls "$DEST"/bin/python3.* 2>/dev/null | head -1 || true)
if [ -n "$PY" ] && [ -x "$PY" ]; then
  echo "already extracted at $DEST, skip"; ls "$DEST"/bin/ | head; exit 0
fi

echo "=== extracting (stream cat | tar -> $DEST) ==="
cd "$DIST"
time cat vllm-rocm-gfx1151.part01.tar.gz vllm-rocm-gfx1151.part02.tar.gz | tar -xzf - -C "$DEST"

echo "=== sanity ==="
ls "$DEST"/ | head -8
PY=$(ls "$DEST"/bin/python3.* | head -1)
"$PY" --version
echo "PY_PATH=$PY"
echo "EXTRACT_DONE"
