#!/bin/bash
# a4_restore.sh — A4: bench 后恢复 llama.cpp 主力服务, 停 vLLM/Ray
# 在 B站 执行 (或经主控站 ssh): bash a4_restore.sh
set -x
# 停 vLLM (launcher 是前台 exec, 直接 pkill api_server / vllm)
pkill -f 'vllm.entrypoints' 2>/dev/null || true
pkill -f 'ray::' 2>/dev/null || true
PY=$(ls /home/scott-lau/vllm-rocm/bin/python3.* 2>/dev/null | head -1)
[ -n "$PY" ] && [ -x "$PY" ] && "$PY" -m ray stop -f 2>/dev/null || true
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local \
  "pkill -f 'ray::' 2>/dev/null; WPY=\$(ls /home/scott-lau/vllm-rocm/bin/python3.* 2>/dev/null | head -1); [ -n \"\$WPY\" ] && [ -x \"\$WPY\" ] && \"\$WPY\" -m ray stop -f 2>/dev/null; sudo systemctl start rpc-server" 2>/dev/null || true
sleep 2
sudo systemctl start llama-server
sleep 3
echo "B: $(systemctl is-active llama-server)"
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local "echo 'A: $(systemctl is-active rpc-server)'"
# 冒烟
sleep 8
curl -s http://127.0.0.1:8080/health && echo " LLAMA_API_OK" || echo "LLAMA_API_PENDING(check B log)"
