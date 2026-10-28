#!/bin/bash
E=/home/scott-lau/llama.cpp-vulkan-b10715/llama-server
echo "=== b10715 version ==="
"$E" --version 2>&1 | head -2
echo "=== draft-mtp strings ==="
strings "$E" 2>/dev/null | grep -ai 'spec-type\|draft-mtp\|draft-mtp-simple\|spec-draft-n-max\|display-decode-log' | head -10
echo "=== qwen35 arch string ==="
strings "$E" 2>/dev/null | grep -ai 'qwen35\|qwen3.5' | head -8
echo "=== master engine if present ==="
for p in /home/scott-lau/.unsloth/studio/lib/llama-server /home/scott-lau/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server; do
  [ -x "$p" ] && echo "-- $p --" && strings "$p" 2>/dev/null | grep -ai 'draft-mtp-simple\|spec-type' | head -4
done