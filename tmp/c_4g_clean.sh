#!/bin/bash
# C 站: 停 qwen 服务 + 清理 + 确认 4G 档释放
set +e
echo "=== 1. 停止 qwen systemd 服务 ==="
sudo -n systemctl stop llama-server@qwen3.8-27b-mtp.service 2>&1
sudo -n systemctl disable llama-server@qwen3.8-27b-mtp.service 2>&1 | tail -2
echo "--- 服务状态 ---"
systemctl is-active llama-server@qwen3.8-27b-mtp.service 2>/dev/null
systemctl is-enabled llama-server@qwen3.8-27b-mtp.service 2>/dev/null
echo ""
echo "=== 2. 强清残留进程 ==="
pkill -9 -f llama-server 2>/dev/null
pkill -9 -f '18080' 2>/dev/null
sleep 3
pgrep -af llama-server || echo '(无 llama-server)'
echo ""
echo "=== 3. 端口 ==="
ss -tlnp 2>/dev/null | grep -E '18080|18081|18082' || echo '(18080/81/82 全释放)'
echo ""
echo "=== 4. VRAM/GTT 释放确认 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo ""
echo "=== 5. 内存 ==="
free -g | head -2
echo ""
echo "=== 6. load-gate (gpt-oss 预检) ==="
bash /tmp/load-gate 60 2>&1 | tail -3