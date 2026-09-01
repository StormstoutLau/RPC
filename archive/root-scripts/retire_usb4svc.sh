#!/bin/bash
# retire_usb4svc.sh — 禁用冗余 usb4-network.service (netplan 已接管 TB 管理)
echo "=== 禁用前确认: netplan connection 活跃 ==="
nmcli -f DEVICE,STATE device show thunderbolt0 2>/dev/null | head -2
sudo systemctl disable usb4-network.service 2>&1
sudo systemctl reset-failed usb4-network.service 2>&1
echo "=== 禁用后状态 ==="
systemctl is-enabled usb4-network.service 2>&1
systemctl is-active usb4-network.service 2>&1
echo "=== 功能回归验证: TB 链路仍通 ==="
ip -br addr show thunderbolt0
ping -c 2 -W 2 10.10.10.1 | tail -1