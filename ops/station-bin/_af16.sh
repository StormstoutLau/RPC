#!/bin/bash
cd /home/scott-lau
pkill -9 -x llama-server 2>/dev/null
pkill -9 -f "unsloth .studio run" 2>/dev/null
sleep 3
export LLAMA_SERVER_PATH=/home/scott-lau/llama.cpp-vulkan-b10715/llama-server
nohup ~/.local/bin/unsloth studio run --model /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 8080 --api-only --parallel 4 --flash-attn on --no-context-shift -c 131072 \
  --device Vulkan0 --kv-unified \
  --chat-template-kwargs '{"reasoning_effort":"low"}' \
  > /home/scott-lau/.unsloth/run-gpt-f16.log 2>&1 &
echo "launched pid=$!"
sleep 2
free -g | head -2