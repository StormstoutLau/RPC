#!/bin/bash
# probe hf-mirror for Qwen3.8-27B GGUF repos (2026-09-06)
for r in "lmstudio-community/Qwen3.8-27B-Instruct-GGUF" \
         "unsloth/Qwen3.8-27B-GGUF" \
         "Qwen/Qwen3.8-27B" \
         "bartowski/Qwen3.8-27B-Instruct-GGUF" \
         "Jackrong/Qwen3.8-27B-MTP-GGUF"; do
  code=$(curl -s -o /tmp/_q27.json -w '%{http_code}' "https://hf-mirror.com/api/models/${r}/tree/main" 2>/dev/null)
  echo "=== ${r}  HTTP=${code}"
  if [ "$code" = "200" ]; then
    grep -o '"path":"[^"]*\.gguf"' /tmp/_q27.json | head -8
  fi
done