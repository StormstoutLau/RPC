#!/bin/bash
# probe DavidAU qwen3.8 repos + file listing on hf-mirror (2026-09-06)
M="https://hf-mirror.com"
echo "=== user repos (qwen3.8) ==="
curl -s "$M/api/models?author=DavidAU&search=qwen3.8&limit=50" 2>/dev/null | grep -o '"id":"[^"]*"' | sort -u | head -30
echo
echo "=== files in MTP GGUF repo ==="
curl -s "$M/api/models/DavidAU/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-MTP-GGUF/tree/main" 2>/dev/null | tr ',' '\n' | grep -E '"path"|"size"' | paste - - 2>/dev/null | head -60