#!/bin/bash
echo "== B 状态 =="
uptime | head -1
free -g | head -2
echo "== llama-gguf-split 帮助 =="
/opt/llama.cpp/llama-gguf-split --help 2>&1 | head -30
echo "== 磁盘 =="
df -h /data 2>/dev/null | tail -1