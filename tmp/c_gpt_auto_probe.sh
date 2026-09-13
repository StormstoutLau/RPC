#!/bin/bash
# C 站: gpt-oss-120b 加载实验 — 监控权重分配走 VRAM(carveout) 还是 GTT(系统内存)
# 自动保护: 系统 avail < 10G 立即 kill; 若走 VRAM(安全) 则继续
set +e
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
LOG=/tmp/c_gpt_auto.log

echo "=== 0. 基线 ==="
free -g | head -2
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used_baseline='
cat /sys/class/drm/card1/device/mem_info_gtt_used  2>/dev/null | xargs echo 'gtt_used_baseline='

echo "=== 1. 清理 ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null; sleep 2

echo "=== 2. 启动 gpt-oss HIP (Auto 档) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m $MODEL --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID"

echo "=== 3. 每 4s 采样分配走向 (最多 20 次, 至 model loaded 止) ==="
for i in $(seq 1 20); do
  sleep 4
  AVAIL=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo)
  VRAM=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null)
  GTT=$(cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null)
  VRAMG=$(awk -v v="$VRAM" 'BEGIN{printf "%.1f", v/1073741824}')
  GTTG=$(awk -v g="$GTT" 'BEGIN{printf "%.1f", g/1073741824}')
  STAT=$(ps -o stat= -p $PID 2>/dev/null)
  LOADED=$(grep -c 'model loaded' "$LOG" 2>/dev/null)
  echo "t=${i} avail=${AVAIL}G vram=${VRAMG}G gtt=${GTTG}G stat=${STAT} loaded=${LOADED}"
  if [ "$LOADED" -ge 1 ]; then echo "== MODEL LOADED =="; break; fi
  if [ "$AVAIL" -lt 10 ]; then
    echo "!! 系统内存危险 (avail=${AVAIL}G < 10G), 走 GTT 路径, 中止加载"
    pkill -9 -f 'gpt-oss-120b'
    break
  fi
  if ! kill -0 $PID 2>/dev/null; then echo "== 进程退出 =="; break; fi
done

echo "=== 4. 结果 ==="
tail -6 "$LOG"
echo "--- 端口 ---"
ss -tlnp 2>/dev/null | grep 18081 || echo '(not listening)'
echo "--- 内存 ---"
free -g | head -2