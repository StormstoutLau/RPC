#!/bin/bash
# C 站: UMA=4G 档 gpt-oss-120b HIP 加载验证
set +e
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
LOG=/tmp/c_gpt_4g.log
echo "=== 0. 基线 ==="
free -g | head -2
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo "=== 1. 清理 ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null; sleep 2
echo "=== 2. 启动 gpt-oss HIP (4G 档) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m $MODEL --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID"
echo "=== 3. 每 5s 采样 (最多 36 次) ==="
for i in $(seq 1 36); do
  sleep 5
  AVAIL=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo)
  VRAM=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null)
  GTT=$(cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null)
  VRAMG=$(awk -v v="$VRAM" 'BEGIN{printf "%.1f", v/1073741824}')
  GTTG=$(awk -v g="$GTT" 'BEGIN{printf "%.1f", g/1073741824}')
  LOADED=$(grep -c 'model loaded' "$LOG" 2>/dev/null)
  ERR=$(grep -cE 'unable to allocate|failed to load|error loading model|out of memory' "$LOG" 2>/dev/null)
  echo "t=${i} avail=${AVAIL}G vram=${VRAMG}G gtt=${GTTG}G loaded=${LOADED} err=${ERR}"
  if [ "$LOADED" -ge 1 ]; then echo "== MODEL LOADED =="; break; fi
  if [ "$ERR" -ge 1 ]; then echo "== LOAD FAILED =="; break; fi
  if ! kill -0 $PID 2>/dev/null; then echo "== 进程退出 =="; break; fi
done
echo "=== 4. 结果 ==="
tail -10 "$LOG"
echo "--- 18081 ---"
ss -tlnp 2>/dev/null | grep 18081 | head -1 | sed 's/users:.*/:(up)/' || echo '(not listening)'
echo "--- 内存 ---"
free -g | head -2