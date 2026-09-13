#!/bin/bash
# 彻底关闭 llama-server 看门狗: 模板 Restart=no + 停服务 + 验证不再自启
set +e
echo "=== 1. 备份模板 ==="
sudo -n cp /etc/systemd/system/llama-server@.service /etc/systemd/system/llama-server@.service.bak-watchdog-20260908 && echo '备份 OK'
echo "=== 2. 修改 Restart=on-failure -> no ==="
sudo -n sed -i 's/^Restart=on-failure/Restart=no/' /etc/systemd/system/llama-server@.service
grep -nE 'Restart|RestartSec' /etc/systemd/system/llama-server@.service
echo "=== 3. daemon-reload ==="
sudo -n systemctl daemon-reload && echo 'reload OK'
echo "=== 4. 停止 qwen 服务 ==="
sudo -n systemctl stop llama-server@qwen3.8-27b-mtp.service 2>&1
sleep 3
echo "--- stop 后 3s 状态 ---"
systemctl is-active llama-server@qwen3.8-27b-mtp.service 2>/dev/null
echo "--- stop 后 15s 状态 (验证不被拉回) ---"
sleep 12
systemctl is-active llama-server@qwen3.8-27b-mtp.service 2>/dev/null
pgrep -af llama-server || echo '(无 llama-server 进程, 看门狗已关闭)'
echo "=== 5. VRAM 释放确认 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
echo "=== 6. 端口 18080 ==="
ss -tlnp 2>/dev/null | grep 18080 || echo '(18080 已释放)'
echo "=== 7. 内存 ==="
free -g | head -2