#!/bin/bash
# B station: RPC dual-node client -> A(10.10.10.1:50052) + C(10.10.11.3:50052)
set -u
BIN=/home/scott-lau/llama.cpp/build/bin/llama-server
MODEL=/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF/Qwen3.8-27B-MTP-Q8_0.gguf
MMPROJ=/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF/mmproj-F32.gguf
pkill -x llama-server 2>/dev/null
sleep 2
nohup "$BIN" \
  -m "$MODEL" --mmproj "$MMPROJ" \
  --rpc 10.10.10.1:50052,10.10.11.3:50052 \
  -c 8192 --no-context-shift --jinja \
  --device Vulkan0 -ngl 99 -t 16 \
  --host 127.0.0.1 --port 18081 \
  > ~/rpc_client_b2.log 2>&1 &
echo "CLIENT_PID=$!"
exit 0