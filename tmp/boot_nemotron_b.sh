#!/bin/bash
# B 站单机加载 Nemotron-3-Super-120B-A12B-Q4_K_M (unsloth HIP/ROCm0, 81G) — domain_matrix 测试
# usage: bash /tmp/boot_nemotron_b.sh [port]
set -uo pipefail
PORT="${1:-8095}"
U=/home/scott-lau/.unsloth/llama.cpp/llama-server
M=/home/scott-lau/.lmstudio/models/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf
LOG=/tmp/nem_b_launch.log
OUT=/tmp/nem_b_run.log

echo "=== [1] load-gate (need=85) ==="
/usr/local/bin/load-gate 85 2>&1
[ $? -eq 0 ] || { echo "ABORT"; exit 1; }

echo "=== [2] 清理旧实例 ==="
pkill -x llama-server 2>/dev/null
sleep 3

echo "=== [3] 启动 llama-server (HIP/ROCm0, ${PORT}) ==="
setsid nohup "$U" \
  -m "$M" --alias Nemotron-3-Super-120B \
  --host 0.0.0.0 --port "$PORT" \
  -c 65536 --flash-attn on --no-context-shift --device ROCm0 \
  -ngl 999 -sm none --kv-unified -np 1 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -b 2048 -ub 2048 --cache-ram 0 \
  --temp 0.6 --top-k 40 --top-p 0.95 \
  --log-file "$OUT" > "$LOG" 2>&1 &
echo $! > /tmp/nem_b.pid
echo "pid=$(cat /tmp/nem_b.pid) log=$OUT"

echo "=== [4] 等待 ready (最长 600s) ==="
for i in $(seq 1 200); do
  s=$(pgrep -x llama-server | head -1)
  if [ -n "$s" ] && curl -sf --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "READY OK :${PORT}"
    ps -o pid,rss,comm -p "$s" 2>/dev/null
    free -g | head -2
    exit 0
  fi
  sleep 3
done
echo "ERROR: 超时"
exit 1