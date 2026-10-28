#!/bin/bash
echo "== 清理 =="
pkill -9 -f "[u]nsloth studio run" 2>/dev/null || true
pkill -9 -x llama-server 2>/dev/null || true
sleep 4
free -g | head -2
echo "== 启动 infer-load gpt-oss-120b (unsloth, CTX=131072) =="
infer-load 'gpt-oss-120b$' 2>&1 | head -30