#!/bin/bash
# check B station llama.cpp engine MTP/spec-decode support + architecture of qwen3.8
echo "=== which llama-server ==="
which llama-server 2>/dev/null; ls -la /usr/local/bin/llama-server 2>/dev/null
echo "=== LLAMA_SERVER_PATH (unsloth engine) ==="
echo "LLAMA_SERVER_PATH=$LLAMA_SERVER_PATH"
P=$(command -v llama-server); [ -z "$P" ] && P="$LLAMA_SERVER_PATH"
echo "using=$P"
[ -n "$P" ] && [ -x "$P" ] && echo "--- $P version ---" && "$P" --version 2>&1 | head -4
echo "=== str contains draft-mtp / spec-draft / MTP ==="
if [ -n "$P" ] && [ -x "$P" ]; then
  grep -ac 'draft-mtp\|spec-draft\|ltp\|GGML_TYPE'A "$P" 2>/dev/null
  strings "$P" 2>/dev/null | grep -ai 'draft-mtp\|spec-draft-n-max\|spec-type' | head -8
fi
echo "=== llama.cpp dirs / git head ==="
for d in /home/scott-lau/llama.cpp /home/scott-lau/llama.cpp-vulkan-b10715 /home/scott-lau/.local/opt/llama.cpp; do
  [ -d "$d" ] && echo "-- $d --" && (git -C "$d" log --oneline -1 2>/dev/null || echo "no-git")
done
echo "=== grep draft-mtp in llama.cpp sources ==="
grep -rl 'draft-mtp\|spec-draft-n-max' /home/scott-lau/llama.cpp 2>/dev/null | head -5
echo "=== qwen3.8 arch in master sources ==="
grep -rn 'qwen3_5\|Qwen3_5\|qwen3.8' /home/scott-lau/llama.cpp/src/llama-arch.cpp 2>/dev/null | head -8