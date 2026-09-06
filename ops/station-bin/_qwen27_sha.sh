#!/bin/bash
# fetch expected sha256 for the two GGUF files from hf-mirror LFS server-metadata
for f in "Qwen3.8-27B-MTP-Q8_0.gguf" "mmproj-F32.gguf"; do
  echo "==== $f"
  curl -sL "https://hf-mirror.com/Jackrong/Qwen3.8-27B-MTP-GGUF/resolve/main/$f" -o /dev/null -r 0-0 2>/dev/null
  # use header metadata
  sha=$(curl -sIL "https://hf-mirror.com/Jackrong/Qwen3.8-27B-MTP-GGUF/resolve/main/$f" 2>/dev/null | grep -i 'x-linked-size\|ETag' | head -3)
  echo "$sha"
done
echo "also list size via tree"
curl -s "https://hf-mirror.com/api/models/Jackrong/Qwen3.8-27B-MTP-GGUF/tree/main" 2>/dev/null | grep -o '"path":"Qwen3.8-27B-MTP-Q8_0.gguf"[^}]*"size":[0-9]*' | head -1
curl -s "https://hf-mirror.com/api/models/Jackrong/Qwen3.8-27B-MTP-GGUF/tree/main" 2>/dev/null | grep -o '"path":"mmproj-F32.gguf"[^}]*"size":[0-9]*' | head -1