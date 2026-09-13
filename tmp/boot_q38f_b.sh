#!/bin/bash
# B 站单机加载 Qwen3.8-Flash-Next UD-IQ4_XS (unsloth HIP, 93.7G) — 给足思考预算测试
# usage: bash /tmp/boot_q38f_b.sh [port]
set -uo pipefail
PORT="${1:-8094}"
U=/home/scott-lau/.unsloth/llama.cpp/llama-server
M=/home/scott-lau/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
LOG=/tmp/q38f_b_launch.log
OUT=/tmp/q38f_b_run.log

echo "=== [1] load-gate (need=94) ==="
/usr/local/bin/load-gate 94 2>&1
[ $? -eq 0 ] || { echo "ABORT: load-gate 未过"; exit 1; }

echo "=== [2] 清理旧实例 ==="
pkill -x llama-server 2>/dev/null
sleep 3

echo "=== [3] 启动 llama-server (HIP/ROCm0, 8094) ==="
setsid nohup "$U" \
  -m "$M" --alias Qwen3.8-Flash-Next \
  --host 0.0.0.0 --port "$PORT" \
  -c 32768 --flash-attn on --no-context-shift --device ROCm0 \
  -ngl 999 -sm none --kv-unified -np 1 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -b 1024 -ub 1024 --cache-ram 0 \
  --reasoning-effort high --reasoning-budget 4000 \
  --log-file "$OUT" > "$LOG" 2>&1 &
echo $! > /tmp/q38f_b.pid
echo "pid=$(cat /tmp/q38f_b.pid) log=$OUT"

echo "=== [4] 等待 ready (最长 420s) ==="
for i in $(seq 1 140); do
  s=$(pgrep -x llama-server | head -1)
  if [ -n "$s" ] && curl -sf --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "READY OK :${PORT} (${i}x3s)"
    ps -o pid,rss,comm -p "$s" 2>/dev/null
    free -g | head -2
    exit 0
  fi
  sleep 3
done
echo "ERROR: 超时未就绪 — tail $OUT $LOG"
tail -20 "$LOG" 2>/dev/null
exit 1