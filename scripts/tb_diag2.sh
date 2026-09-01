#!/bin/bash
# 换线后 TB 深度诊断: controller 状态 + BIOS 重置检测
echo "=== 开机时间 ==="
uptime -s; uptime
echo
echo "=== 内存 (BIOS UMA 检测: ~124G=正常 0.5G carve-out / ~32G=BIOS 重置回 96G) ==="
free -g | sed -n '2p'
echo
echo "=== TB domain 详情 ==="
for d in /sys/bus/thunderbolt/devices/domain*; do
  echo "$(basename $d): security=$(cat $d/security 2>/dev/null) nvm=$(cat $d/nvm_version 2>/dev/null) iommu=$(cat $d/iommu_dma_protection 2>/dev/null)"
done
echo
echo "=== host router 状态 ==="
for d in /sys/bus/thunderbolt/devices/*-*; do
  echo "$d: authorized=$(cat $d/authorized 2>/dev/null) gen=$(cat $d/generation 2>/dev/null)"
done
echo
echo "=== usb4_port 目录内容 (端口是否检测到对端) ==="
for p in /sys/bus/thunderbolt/devices/*/usb4_port*; do
  echo "--- $p:"
  ls "$p" 2>/dev/null | sed 's/^/    /'
done
echo
echo "=== 本次开机全部 TB/USB4 内核事件 ==="
journalctl -k -b --no-pager 2>/dev/null | grep -iE 'thunderbolt|usb4|config error|tb[0-9]' | tail -25
echo "(若空则零事件)"
