#!/bin/bash
# start DavidAU q4k ad-hoc on 18081 (coexist with Jackrong 18080) (2026-09-06)
M=/data/models/gguf/davidau-q38-27b-q4k/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q4_K_M.gguf
P=/data/models/gguf/davidau-q38-27b-q4k/mmproj-BF16.gguf
BIN=/home/scott-lau/llama.cpp/build/bin/llama-server
nohup "$BIN" -m "$M" --mmproj "$P" -c 8192 -t 16 -ngl 999 \
  --flash-attn on --device Vulkan0 --parallel 1 --no-context-shift \
  --host 0.0.0.0 --port 18081 > /tmp/davidau_srv.log 2>&1 &
echo "launched pid=$!"
echo "=== early log ==="
sleep 20
tail -8 /tmp/davidau_srv.log
echo "=== health ==="
curl -s --max-time 3 http://127.0.0.1:18081/health; echo