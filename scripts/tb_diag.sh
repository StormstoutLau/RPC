#!/bin/bash
# 换线后 TB controller 排查: PCI 层是否存在 + 各域状态
echo "=== lspci (USB/网络/TB 相关) ==="
lspci | grep -iE 'usb|ethernet|network|thunderbolt|bridge' | head -20
echo
echo "=== TB sysfs 实际路径 ==="
find /sys/devices -name '*thunderbolt*' -maxdepth 6 2>/dev/null | head -10
echo
echo "=== domain0/1 详情 ==="
for d in /sys/bus/thunderbolt/devices/domain*; do
  echo "--- $d ---"
  cat "$d/active" 2>/dev/null && echo " (active)"
  cat "$d/iommu_dma_protection" 2>/dev/null
done
echo
echo "=== 0-0 / 1-0 (host router) 详情 ==="
for d in /sys/bus/thunderbolt/devices/0-0 /sys/bus/thunderbolt/devices/1-0; do
  echo "--- $d ---"
  cat "$d/nhi" 2>/dev/null
  ls "$d" 2>/dev/null | tr '\n' ' '; echo
done
echo
echo "=== net driver 绑定 (enp197s0 是谁?) ==="
ethtool -i enp197s0 2>/dev/null | head -3
ip -d link show enp197s0 2>/dev/null | head -3
