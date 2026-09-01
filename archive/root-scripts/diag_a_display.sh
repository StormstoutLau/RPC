#!/bin/bash
# diag_a_display.sh — A 站重启后排查: 内核确认 + 显示 + USB4
A="scott-lau@10.10.10.1"
echo "=== [0] A 站可达? ==="
ping -c 2 -W 2 10.10.10.1 | tail -1

echo "=== [1] 内核/启动 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "内核: $(uname -r)"
  echo "启动时间: $(uptime -p)"
  echo "上次启动日志尾部 (切换是否干净): "
  sudo journalctl -b -1 --no-pager | tail -3 | cut -c1-100
'

echo "=== [2] 显示状态 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  export DISPLAY=:0; export XAUTHORITY=$(ls /run/user/*/gdm/Xauthority 2>/dev/null | head -1)
  echo "--- xrandr 连接器与模式 ---"
  xrandr 2>/dev/null | head -25 || echo "(xrandr 失败: 无 X 会话或权限)"
  echo "--- amdgpu 显示相关 dmesg ---"
  sudo dmesg | grep -iE "amdgpu|drm" | grep -iE "connect|encoder|mode|crtc|display|link|dp |hdmi" | tail -12
'

echo "=== [3] USB4/TB 状态 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "--- thunderbolt netdev ---"
  ip -br addr show | grep -E "thunderbolt|10.10.10" || echo "(无 TB 网络接口!)"
  echo "--- TB 设备树 ---"
  sudo dmesg | grep -iE "thunderbolt" | tail -8
  echo "--- USB4 host ---"
  ls /sys/bus/thunderbolt/devices/ 2>/dev/null | head -8
'