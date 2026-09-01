#!/bin/bash
# L1c-A: A 站 netconsole 加载 + 持久化 (printk 镜像到 B 站 10.10.10.2:6665)
set -u
exec 2>&1

sudo tee /etc/modprobe.d/netconsole.conf >/dev/null <<'EOF'
# A 站 printk 镜像到 B 站 (USB4 直连, 挂死取证通道, 2026-09-01)
options netconsole netconsole=6665@/10.10.10.1/thunderbolt0,6665@10.10.10.2/02:66:bd:12:dc:35
EOF

echo netconsole | sudo tee /etc/modules-load.d/netconsole.conf >/dev/null

# 立即加载 (接口已 UP)
sudo modprobe netconsole 2>&1 || echo "(可能已加载)"
echo "--- 模块状态 ---"
lsmod | grep netconsole || echo "!! 未加载"
echo "--- netconsole 启动日志 ---"
sudo dmesg | grep -i netconsole | tail -5
echo "--- 发送测试消息 ---"
echo "netconsole-test-from-A $(date '+%H:%M:%S')" | sudo tee /dev/kmsg
echo "DONE_L1C_A"
