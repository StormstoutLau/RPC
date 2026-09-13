#!/bin/bash
# 步骤1: 确认 carveout 干净 -> 直接重试 gpt-oss HIP (不恢复 qwen)
set +e
echo "=== 0. 前置确认 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
ss -tlnp 2>/dev/null | grep -E '18080|18081' || echo '(18080/18081 均未监听)'
free -g | head -2

echo "=== 1. load-gate (系统内存侧预检) ==="
bash /tmp/load-gate 60 2>&1 | tail -3

echo "=== 2. 清理残留 ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
pkill -9 -f 'ROCm0' 2>/dev/null
sleep 2

echo "=== 3. 启动 gpt-oss HIP (Auto 档, carveout 干净) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_auto3.log 2>&1 &
PID=$!
echo "pid=$PID"

echo "=== 4. 每 5s 采样 (最多 30 次) ==="
for i in $(seq 1 30); do
  sleep 5
  AVAIL=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo)
  VRAM=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null)
  GTT=$(cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null)
  VRAMG=$(awk -v v="$VRAM" 'BEGIN{printf "%.1f", v/1073741824}')
  GTTG=$(awk -v g="$GTT" 'BEGIN{printf "%.1f", g/1073741824}')
  LOADED=$(grep -c 'model loaded' /tmp/c_gpt_auto3.log 2>/dev/null)
  ERR=$(grep -cE 'unable to allocate|failed to load|error loading' /tmp/c_gpt_auto3.log 2>/dev/null)
  echo "t=${i} avail=${AVAIL}G vram=${VRAMG}G gtt=${GTTG}G loaded=${LOADED} err=${ERR}"
  if [ "$LOADED" -ge 1 ]; then echo "== MODEL LOADED =="; break; fi
  if [ "$ERR" -ge 1 ] && [ "$i" -ge 2 ]; then echo "== LOAD FAILED =="; break; fi
  if ! kill -0 $PID 2>/dev/null; then echo "== 进程退出 =="; break; fi
done

echo "=== 5. gpt 日志尾部 ==="
tail -8 /tmp/c_gpt_auto3.log
echo "--- 18081 ---"
ss -tlnp 2>/dev/null | grep 18081 | head -1 | sed 's/users:.*/:(up)/' || echo '(not listening)'
echo "--- 内存 ---"
free -g | head -2