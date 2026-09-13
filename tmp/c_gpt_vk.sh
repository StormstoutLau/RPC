#!/bin/bash
# C 站: gpt-oss-120b Vulkan 测试 (与 HIP 同参数对照)
set +e
ENGINE=/home/scott-lau/llama.cpp/build/bin/llama-server
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
LOG=/tmp/c_gpt_vk.log
echo "=== 0. baseline ==="
free -g | head -2
echo "=== 1. 启动 gpt-oss Vulkan (Vulkan0, -ngl 999 全 offload) ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null; sleep 2
setsid nohup $ENGINE -m $MODEL --port 18083 --device Vulkan0 -ngl 999 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID"
echo "=== 2. 采样 (最多 42 次, 每 5s) ==="
for i in $(seq 1 42); do
  sleep 5
  AVAIL=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo)
  LOADED=$(grep -c 'model loaded' "$LOG" 2>/dev/null)
  ERR=$(grep -cE 'failed|error|out of memory' "$LOG" 2>/dev/null)
  echo "t=${i} avail=${AVAIL}G loaded=${LOADED} err=${ERR}"
  if [ "$LOADED" -ge 1 ]; then echo "== MODEL LOADED =="; break; fi
  if [ "$ERR" -ge 1 ] && [ "$i" -ge 3 ]; then echo "== LOAD FAILED =="; break; fi
  if ! kill -0 $PID 2>/dev/null; then echo "== 进程退出 =="; break; fi
done
echo "=== 3. 日志尾部 ==="
tail -10 "$LOG"
echo "--- 18083 ---"
ss -tlnp 2>/dev/null | grep 18083 | head -1 | sed 's/users:.*/:(up)/' || echo '(not listening)'
echo "--- 内存 ---"
free -g | head -2