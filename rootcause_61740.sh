#!/bin/bash
# rootcause_61740.sh — 采集 6.17.0-40 启动 (-b -1) 的网络/显示证据
A="scott-lau@10.10.10.1"
echo "=== [1] 当前状态 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "当前内核: $(uname -r); host: $(hostname)"
  ip -br addr | head -8
'
echo
echo "=== [2] 6.17.0-40 那次启动: 网卡驱动与固件 ==="
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  sudo journalctl -b -1 -k --no-pager | grep -iE "r8169|realtek|igc|igb|e1000|firmware|NIC|net |link is|eth" | head -20
  echo "--- 网络接口列表 (-b -1 的 userspace 日志) ---"
  sudo journalctl -b -1 --no-pager | grep -iE "NetworkManager|netplan|systemd-networkd" | grep -iE "device|interface|carrier|managed" | head -12
'
echo
echo "=== [3] 6.17.0-40 那次启动: USB4/TB ==="
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  sudo journalctl -b -1 -k --no-pager | grep -iE "thunderbolt|usb4|xhci" | head -15
'
echo
echo "=== [4] 6.17.0-40 那次启动: amdgpu 显示 ==="
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  sudo journalctl -b -1 -k --no-pager | grep -iE "amdgpu|drm" | grep -iE "hpd|connector|edid|mode|crtc|link|dp|hdmi|dsc" | head -15
'
echo
echo "=== [5] 6.17.0-40 那次启动尾部 (切换是否干净) ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A 'sudo journalctl -b -1 --no-pager | tail -4 | cut -c1-90'