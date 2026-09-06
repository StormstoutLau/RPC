#!/bin/bash
# 收编嵌套下载的 DavidAU 文件 (aria2 -d + 绝对-o 拼接成 DEST/data/...) (2026-09-06)
set -u
DEST=/data/models/gguf/davidau-q38-27b-q4k
SRC="$DEST/data/models/gguf/davidau-q38-27b-q4k"
declare -A FILES=(
  ["Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf"]="43c980bb2f5e6f712b55b5bb2a154b427c20e8f595d6a84365fc85725512dbc7|18047253056"
  ["mmproj-BF16.gguf"]="734916669e61e798d2af7cdbff50ef7b1520b66993b69089bb883048cc048929|931145888"
)
ls -la "$SRC" 2>&1
for name in "${!FILES[@]}"; do
  srcp="$SRC/$name.tmp"
  dstp="$DEST/$name"
  [ -f "$srcp" ] || { echo "MISSING $srcp"; exit 4; }
  mv -f "$srcp" "$dstp" || { echo "MV FAIL $dstp"; exit 4; }
  exp_sha="${FILES[$name]%%|*}"; exp_size="${FILES[$name]##*|}"
  act_size=$(stat -c%s "$dstp")
  act_sha=$(sha256sum "$dstp" | awk '{print $1}')
  echo "$name size=$act_size (exp $exp_size) sha=${act_sha:0:16}..."
  [ "$act_size" = "$exp_size" ] || { echo "SIZE MISMATCH"; exit 5; }
  [ "$act_sha" = "$exp_sha" ] || { echo "SHA MISMATCH act=$act_sha exp=$exp_sha"; exit 5; }
  echo "VERIFIED OK $name"
done
# 清理嵌套空目录
rmdir -p "$SRC" 2>/dev/null
echo "=== final ==="
ls -la "$DEST"