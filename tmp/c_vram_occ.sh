#!/bin/bash
# C 站: 排查 30.6G VRAM 占用来源 + 释放后重试
set +e
echo "=== 1. VRAM/GTT 占用现状 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo "=== 2. 什么进程持有 GPU 内存 ==="
echo '-- 尝试 drm debug --'
sudo -n cat /sys/kernel/debug/dri/1/drm_gem 2>/dev/null | head -5 || echo '(不可读)'
echo "=== 3. 运行中 llama/显示进程 ==="
ps -eo pid,rss,comm | grep -iE 'llama|Xorg|wayland|kwin|gnome-shell|plasma' | head -10
echo "--- qwen 18080 RSS ---"
QPID=$(ss -tlnp 2>/dev/null | grep 18080 | grep -oP 'pid=\K[0-9]+' | head -1)
echo "qwen pid=$QPID"; ps -o rss= -p $QPID 2>/dev/null | xargs echo 'qwen rss(MB)='
echo "=== 4. rocm-smi / amd-smi GPU 内存占用 ==="
which rocm-smi amd-smi 2>/dev/null || echo '(无 rocm-smi, ROCm 已移除)'
echo "=== 5. KFD 进程列表 ==="
sudo -n cat /sys/kernel/debug/kfd/proc_list 2>/dev/null | head -20 || echo '(不可读)'
echo "=== 6. 内存全貌 ==="
free -g | head -2
echo "=== 7. 近期 dmesg 内存相关 ==="
sudo -n dmesg 2>/dev/null | grep -iE 'out of memory|oom|died' | tail -3