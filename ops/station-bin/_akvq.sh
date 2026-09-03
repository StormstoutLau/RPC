#!/bin/bash
cd /home/scott-lau
pkill -9 -x llama-server 2>/dev/null
pkill -9 -f "unsloth .studio run" 2>/dev/null
sleep 3
export LLAMA_SERVER_PATH=/home/scott-lau/llama.cpp-vulkan-b10715/llama-server
free -g > /tmp/kvq-before.txt
nohup ~/.local/bin/unsloth studio run --model /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 8080 --api-only --parallel 4 --flash-attn on --no-context-shift -c 131072 \
  --device Vulkan0 --kv-unified \
  --chat-template-kwargs '{"reasoning_effort":"low"}' \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  > /home/scott-lau/.unsloth/run-gpt-kvq.log 2>&1 &
echo "launched pid=$!"
sleep 2
free -g > /tmp/kvq-before-after.txt
echo "mem-before:"; cat /tmp/kvq-before.txt | head -2