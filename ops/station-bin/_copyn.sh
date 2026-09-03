#!/bin/bash
SRC=scott-lau@scott-lau-GTR-Pro.local:/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF
DST=/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF
mkdir -p "$DST"
for f in NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf \
         NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00002-of-00003.gguf \
         NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00003-of-00003.gguf; do
  if [ -f "$DST/$f" ] && [ "$(stat -c%s "$DST/$f")" -ge 1000 ]; then
    echo "skip existing: $f"
    continue
  fi
  echo ">>> scp $f"
  scp -o BatchMode=yes "$SRC/$f" "$DST/$f" && echo "OK $f"
done
echo "ALL_DONE"; ls -l "$DST"