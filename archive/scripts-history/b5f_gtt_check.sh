#!/bin/bash
# b5f_gtt_check.sh — B 站 amdgpu GTT/VRAM 占用确认
echo "===== $(hostname -s) GTT @ $(date '+%F %T') ====="
for d in /sys/class/drm/card*/device; do
  echo "--- $d ---"
  for f in mem_info_vram_total mem_info_vram_used mem_info_gtt_total mem_info_gtt_used; do
    [ -f "$d/$f" ] && echo "  $f: $(( $(cat $d/$f) / 1048576 )) MB"
  done
done
echo ""
echo "--- llama-server 进程打开的 GPU 设备 ---"
PID=$(pgrep -f 'llama-serve[r]' | head -1)
sudo ls -la /proc/$PID/fd 2>/dev/null | grep -E 'dri|render' | head -5
