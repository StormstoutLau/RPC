#!/bin/bash
# Resume Qwen3.8-27B-MTP-Q8_0.gguf download + sha256 verify (2026-09-06)
# Uses corrected -o basename; resumes from existing .tmp via aria2 -c
set -u
REPO="Jackrong/Qwen3.8-27B-MTP-GGUF"
DEST="/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF"
MIRROR="https://hf-mirror.com"
BN="Qwen3.8-27B-MTP-Q8_0.gguf"
EXP_SHA="ab48c2f5edbdc7068f9f30e886b4964324b5f716aaf07f7af3887f14a377c3f1"
EXP_SIZE="29047084352"

aria2c -c -x16 -s16 --file-allocation=none --max-tries=10 --retry-wait=5 \
   --auto-file-renaming=false --allow-overwrite=false \
   -d "$DEST" -o "$BN.tmp" "$MIRROR/$REPO/resolve/main/$BN"
rc=$?
if [ $rc -ne 0 ]; then echo "FAIL aria2 rc=$rc"; exit $rc; fi
mv -f "$DEST/$BN.tmp" "$DEST/$BN"
act_size=$(stat -c%s "$DEST/$BN")
[ "$act_size" = "$EXP_SIZE" ] || { echo "SIZE MISMATCH act=$act_size exp=$EXP_SIZE"; exit 5; }
act_sha=$(sha256sum "$DEST/$BN" | awk '{print $1}')
[ "$act_sha" = "$EXP_SHA" ] || { echo "SHA256 MISMATCH"; echo "  act=$act_sha"; echo "  exp=$EXP_SHA"; exit 5; }
echo "VERIFIED OK -> $BN (size=$act_size sha=$act_sha)"
echo "=== dest ==="
ls -la "$DEST"
echo "=== DONE ==="