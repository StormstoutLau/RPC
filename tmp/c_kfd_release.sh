#!/bin/bash
# C 站: 确认 qwen HIP 残留并等待 KFD 释放
set +e
echo "=== 0. 当前进程状态 ==="
ps -eo pid,rss,etime,cmd | grep -E 'llama-server' | grep -v grep | head -5
echo "=== 1. vram_used 当前值 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
echo "=== 2. 强制清理所有 HIP 相关 llama 进程 ==="
pkill -9 -f '18082' 2>/dev/null
pkill -9 -f 'qwen3.8-27b-mtp' 2>/dev/null
pkill -9 -f 'ROCm0' 2>/dev/null
sleep 3
echo "-- 清理后进程 --"
ps -eo cmd | grep llama-server | grep -v grep | head -5 || echo '(无)'
echo "=== 3. 等待 KFD 释放 (最多 60s) ==="
for i in $(seq 1 15); do
  V=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null)
  VG=$(awk -v v="$V" 'BEGIN{printf "%.1f", v/1073741824}')
  echo "t=${i} vram_used=${VG}G"
  if [ "$V" -lt 1000000000 ]; then echo "== VRAM 已释放到 <1G =="; break; fi
  sleep 4
done
echo "=== 4. 最终状态 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
free -g | head -2
echo "--- 18080 (qwen Vulkan 保留) ---"
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/users:.*/:(18080 up)/'