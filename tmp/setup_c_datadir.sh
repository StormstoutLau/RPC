#!/bin/bash
# C: create /data/models/gguf/Jackrong structure (align to B) + check build progress
sudo mkdir -p /data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF
sudo chown -R scott-lau:scott-lau /data
echo "=== /data created ==="
ls -la /data/models/gguf/Jackrong/ 2>/dev/null
echo "=== build status ==="
ls ~/llama.cpp/build/bin/llama-server 2>/dev/null && echo BUILD_READY || echo BUILD_PENDING
pgrep -af 'git|cmake|make' 2>/dev/null | head -3 || echo "no build procs"