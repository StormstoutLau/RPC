#!/bin/bash
# Download Qwen3.8-27B-MTP-Q8_0 (Jackrong) + mmproj to B station (2026-09-06)
# Mirror: hf-mirror ; tool: aria2c -x16 ; sha256 verify from tree API fallback
set -u
REPO="Jackrong/Qwen3.8-27B-MTP-GGUF"
DEST="/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF"
mkdir -p "$DEST"
MIRROR="https://hf-mirror.com"
# map local file -> remote path (paths differ for the two)
declare -A FILES=(
  ["$DEST/Qwen3.8-27B-MTP-Q8_0.gguf"]="Qwen3.8-27B-MTP-Q8_0.gguf"
  ["$DEST/mmproj-F32.gguf"]="mmproj-F32.gguf"
)
# expected sha256 (x-linked-etag from hf-mirror, obtained 2026-09-06)
declare -A SHAEXP=(
  ["Qwen3.8-27B-MTP-Q8_0.gguf"]="ab48c2f5edbdc7068f9f30e886b4964324b5f716aaf07f7af3887f14a377c3f1"
  ["mmproj-F32.gguf"]="c077c6d3be3e0a1dcaee66180b2238c33e1a7b34bd920b546e12738202d5ac28"
)
declare -A SIZEEXP=(
  ["Qwen3.8-27B-MTP-Q8_0.gguf"]="29047084352"
  ["mmproj-F32.gguf"]="1842940128"
)
command -v aria2c >/dev/null || { echo "aria2c missing"; exit 3; }
df -h "$DEST" | tail -1
for local in "${!FILES[@]}"; do
  remote="${FILES[$local]}"
  bn=$(basename "$local")
  url="$MIRROR/$REPO/resolve/main/$remote"
  echo "==== download $bn  ($url)"
  aria2c -c -x16 -s16 --file-allocation=none --max-tries=10 --retry-wait=5 \
     --auto-file-renaming=false --allow-overwrite=false \
     -d "$DEST" -o "$bn.tmp" "$url"
  rc=$?
  if [ $rc -eq 0 ]; then
    mv -f "$DEST/$bn.tmp" "$local"
    # verify: size then sha256
    act_size=$(stat -c%s "$local" 2>/dev/null)
    exp_size="${SIZEEXP[$bn]:-}"
    [ -n "$exp_size" ] && [ "$act_size" != "$exp_size" ] && { echo "SIZE MISMATCH $bn act=$act_size exp=$exp_size"; exit 5; }
    act_sha=$(sha256sum "$local" | awk '{print $1}')
    exp_sha="${SHAEXP[$bn]:-}"
    if [ -n "$exp_sha" ] && [ "$act_sha" != "$exp_sha" ]; then
      echo "SHA256 MISMATCH $bn"; echo "  act=$act_sha"; echo "  exp=$exp_sha"; exit 5
    fi
    echo "VERIFIED OK -> $local (size=$act_size sha=$act_sha)"
  else
    echo "FAIL aria2 rc=$rc for $bn"; exit $rc
  fi
done
echo "=== verify sizes ==="
ls -la "$DEST"
echo "=== sha256sum ==="
sha256sum "$DEST"/*.gguf | sed "s#$DEST/##"
echo "=== DONE ==="