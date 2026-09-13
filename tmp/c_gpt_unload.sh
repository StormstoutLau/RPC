#!/bin/bash
# C 站: 1) 卸载 gpt-oss-18081 2) 确认释放
set +e
echo "=== 1. 终止 gpt-oss (pid 5229) ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
pkill -9 -f '18081' 2>/dev/null
sleep 3
pgrep -af llama-server || echo '(无 llama-server)'
echo "=== 2. 端口释放 ==="
ss -tlnp 2>/dev/null | grep -E '18080|18081' || echo '(18080/18081 释放)'
echo "=== 3. VRAM/GTT 释放 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo "=== 4. 内存 ==="
free -g | head -2
echo "=== 5. 等待 10s 确认无自启 ==="
sleep 10
ps -eo pid,etime,cmd | grep llama-server | grep -v grep || echo '(10s 后仍无 llama-server, 无自启)'