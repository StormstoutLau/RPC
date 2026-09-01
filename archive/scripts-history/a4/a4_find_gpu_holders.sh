#!/bin/bash
# a4_find_gpu_holders.sh — 找出仍持有 /dev/dri /dev/kfd 的进程 + GTT 状态
set -uo pipefail
echo "=== fuser /dev/dri/renderD128 ==="
sudo fuser -v /dev/dri/renderD128 2>&1 | head -8
echo "=== fuser /dev/kfd ==="
sudo fuser -v /dev/kfd 2>&1 | head -8
echo "=== lsof (fallback) ==="
sudo lsof /dev/dri/card1 /dev/dri/renderD128 2>/dev/null | awk '{print $1, $2, $NF}' | head -10
echo "=== GTT ==="
cat /sys/class/drm/card*/device/mem_info_gtt_used
echo "=== python procs ==="
pgrep -af python3.14 | head -5 | cut -c1-140
echo "FIND_DONE"
