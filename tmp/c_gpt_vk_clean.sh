#!/bin/bash
# C 站: 停止 Vulkan gpt 实例, 回归干净
set +e
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
sleep 3
pgrep -af llama-server || echo '(无 llama-server)'
ss -tlnp 2>/dev/null | grep 18083 || echo '(18083 释放)'
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
free -g | head -2