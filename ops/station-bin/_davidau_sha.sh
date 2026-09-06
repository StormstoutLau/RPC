#!/bin/bash
# fetch sha256 + size for DavidAU Q4_K_M + mmproj-BF16 via hf-mirror LFS metadata (2026-09-06)
M="https://hf-mirror.com"
REPO="DavidAU/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-MTP-GGUF"
for f in "Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf" "mmproj-BF16.gguf"; do
  echo "==== $f"
  curl -sIL "$M/$REPO/resolve/main/$f" 2>/dev/null | grep -iE 'x-linked-etag|x-linked-size|content-length' | head -3
done