#!/bin/bash
# C 站: 恢复 qwen 18080 (Vulkan) + 重试 gpt-oss HIP (carveout 已干净)
set +e
echo "=== 1. 恢复 qwen 18080 服务 ==="
nohup /home/scott-lau/llama.cpp/build/bin/llama-server \
  -m /home/scott-lau/models/qwen3.8-27b-mtp/Qwen3.8-27B-MTP-Q8_0.gguf \
  -ngl 999 -c 8192 -t 16 --n-cpu-moe 0 \
  --mmproj /home/scott-lau/models/qwen3.8-27b-mtp/mmproj-F32.gguf \
  --flash-attn on --device Vulkan0 --spec-type draft-mtp --spec-draft-n-max 5 \
  --parallel 1 --no-context-shift --jinja \
  --chat-template-file /etc/llama-instances/chat-templates/froggeric_qwen.jinja \
  --host 0.0.0.0 --port 18080 > /tmp/c_qwen_vulkan.log 2>&1 &
echo "qwen pid=$!"
sleep 25
echo "--- 18080 ---"
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/users:.*/:(up)/' || echo '(not yet)'
echo "--- qwen 日志 ---"
tail -4 /tmp/c_qwen_vulkan.log 2>/dev/null

echo ""
echo "=== 2. 确认 carveout 干净后重试 gpt-oss ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used_now='
pkill -9 -f 'gpt-oss-120b' 2>/dev/null; sleep 2
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_auto2.log 2>&1 &
echo "gpt pid=$!"
echo "--- 每 5s 采样 (最多 24 次) ---"
for i in $(seq 1 24); do
  sleep 5
  AVAIL=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo)
  VRAM=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null)
  VRAMG=$(awk -v v="$VRAM" 'BEGIN{printf "%.1f", v/1073741824}')
  LOADED=$(grep -c 'model loaded' /tmp/c_gpt_auto2.log 2>/dev/null)
  ERR=$(grep -cE 'unable to allocate|failed to load|error' /tmp/c_gpt_auto2.log 2>/dev/null)
  echo "t=${i} avail=${AVAIL}G vram=${VRAMG}G loaded=${LOADED} err=${ERR}"
  if [ "$LOADED" -ge 1 ]; then echo "== MODEL LOADED =="; break; fi
  if [ "$ERR" -ge 1 ] && [ "$i" -ge 3 ]; then echo "== 加载失败 =="; break; fi
done
echo "--- gpt 日志尾部 ---"
tail -8 /tmp/c_gpt_auto2.log
echo "--- 18081 ---"
ss -tlnp 2>/dev/null | grep 18081 | head -1 | sed 's/users:.*/:(up)/' || echo '(not listening)'
echo "--- 内存 ---"
free -g | head -2