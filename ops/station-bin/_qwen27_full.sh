#!/bin/bash
# full listing for Qwen3.8-27B candidate repos (2026-09-06)
for r in "unsloth/Qwen3.8-27B-GGUF" "Jackrong/Qwen3.8-27B-MTP-GGUF"; do
  echo "########## ${r} ##########"
  curl -s "https://hf-mirror.com/api/models/${r}/tree/main" 2>/dev/null \
    | grep -o '"path":"[^"]*"\|"size":[0-9]*' \
    | paste - - 2>/dev/null | head -40
done