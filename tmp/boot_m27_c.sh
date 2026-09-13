#!/bin/bash
# C 站加载 MiniMax-M2.7 UD-IQ4_XS (unsloth HIP, ~108G) — 提供 API 端口
set -uo pipefail
PORT="${1:-8093}"
U=/home/scott-lau/.unsloth/llama.cpp/llama-server
M=/home/scott-lau/.lmstudio/models/lmstudio-community/MiniMax-M2.7-GGUF/UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-00001-of-00004.gguf
LOG=/tmp/m27_c_launch.log
OUT=/tmp/m27_c_run.log

echo "=== [1] load-gate (need=105, C站121G内存) ==="
/usr/local/bin/load-gate 105 2>&1
[ $? -eq 0 ] || { echo "ABORT"; exit 1; }

echo "=== [2] 启动 llama-server (HIP/ROCm0, ${PORT}) ==="
pkill -x llama-server 2>/dev/null
sleep 2
setsid nohup "$U" \
  -m "$M" --alias MiniMax-M2.7 \
  --host 0.0.0.0 --port "$PORT" \
  -c 131072 --flash-attn on --no-context-shift --device ROCm0 \
  -ngl 999 -sm none --kv-unified -np 1 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  -b 2048 -ub 2048 --cache-ram 8192 \
  --temp 1.0 --top-k 40 --top-p 0.95 \
  --log-file "$OUT" > "$LOG" 2>&1 &
echo $! > /tmp/m27_c.pid

echo "=== [3] 等待 ready (最长 600s) ==="
for i in $(seq 1 200); do
  if curl -sf --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "READY OK :${PORT}"
    ps -o pid,rss,comm -p "$(cat /tmp/m27_c.pid)" 2>/dev/null
    free -g | head -2
    exit 0
  fi
  sleep 3
done
echo "ERROR: 超时"
exit 1