#!/bin/bash
# Download DavidAU Qwen3.8-27B NEO-Q4_K_M (non-MTP) + mmproj-BF16 to B station (2026-09-06)
# Mirror: hf-mirror ; tool: aria2c ; verify: size + sha256
set -u
REPO="DavidAU/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-MTP-GGUF"
DEST="/data/models/gguf/davidau-q38-27b-q4k"
mkdir -p "$DEST"
MIRROR="https://hf-mirror.com"
declare -A FILES=(
  ["$DEST/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf"]="Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf"
  ["$DEST/mmproj-BF16.gguf"]="mmproj-BF16.gguf"
)
declare -A SHAEXP=(
  ["Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf"]="43c980bb2f5e6f712b55b5bb2a154b427c20e8f595d6a84365fc85725512dbc7"
  ["mmproj-BF16.gguf"]="734916669e61e798d2af7cdbff50ef7b1520b66993b69089bb883048cc048929"
)
declare -A SIZEEXP=(
  ["Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf"]="18047253056"
  ["mmproj-BF16.gguf"]="931145888"
)
command -v aria2c >/dev/null || { echo "aria2c missing"; exit 3; }
df -h "$DEST" | tail -1
for local in "${!FILES[@]}"; do
  remote="${FILES[$local]}"
  url="$MIRROR/$REPO/resolve/main/$remote"
  echo "==== download $local ($url)"
  aria2c -c -x16 -s16 --file-allocation=none --max-tries=10 --retry-wait=5 \
     --auto-file-renaming=false --allow-overwrite=false \
     -d "$DEST" -o "$local.tmp" "$url"
  rc=$?
  if [ $rc -eq 0 ]; then
    act=$(ls "${local}.tmp" 2>/dev/null || echo missing)
    [ "$act" = "missing" ] && mv -f "$DEST/$(basename "$local")" "$local" 2>/dev/null  # .tmp absent if aria2 default-named? safeguard
    [ -f "$local.tmp" ] && mv -f "$local.tmp" "$local"
    act_size=$(stat -c%s "$local" 2>/dev/null)
    exp_size="${SIZEEXP[$local]:-}"
    [ -n "$exp_size" ] && [ "$act_size" != "$exp_size" ] && { echo "SIZE MISMATCH $local act=$act_size exp=$exp_size"; exit 5; }
    act_sha=$(sha256sum "$local" | awk '{print $1}')
    exp_sha="${SHAEXP[$local]:-}"
    if [ -n "$exp_sha" ] && [ "$act_sha" != "$exp_sha" ]; then
      echo "SHA256 MISMATCH $local"; echo "  act=$act_sha"; echo "  exp=$exp_sha"; exit 5
    fi
    echo "VERIFIED OK -> $local (size=$act_size sha=$act_sha)"
  else
    echo "FAIL aria2 rc=$rc for $local"; exit $rc
  fi
done
echo "=== final ==="
ls -la "$DEST"
echo "=== sha256sum ==="
sha256sum "$DEST"/*.gguf | sed "s#$DEST/##"
echo "=== DL-DONE ==="