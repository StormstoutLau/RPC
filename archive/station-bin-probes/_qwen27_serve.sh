#!/bin/bash
# Launch Qwen3.8-27B-MTP-Q8_0 inference instance with new master engine (2026-09-06)
# Mode: user chose "先停 gpt-oss 再测试" — gpt-oss already unloaded, memory free
set -u
ENGINE=/home/scott-lau/llama.cpp/build/bin/llama-server
DEST=/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF
MODEL=$DEST/Qwen3.8-27B-MTP-Q8_0.gguf
MMPROJ=$DEST/mmproj-F32.gguf
PORT=18080
LOG=/tmp/qwen27_serve.log

echo "=== launch $(date '+%F %T') ===" > "$LOG"
nohup "$ENGINE" -m "$MODEL" --mmproj "$MMPROJ" \
  --port "$PORT" --host 127.0.0.1 \
  -c 8192 --flash-attn on --device Vulkan0 -ngl 999 \
  --spec-type draft-mtp --spec-draft-n-max 5 \
  --parallel 1 --no-context-shift \
  >> "$LOG" 2>&1 &
echo "launcher pid=$!" >> "$LOG"
echo "=== DONE-LAUNCH ===" >> "$LOG"