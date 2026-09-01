#!/bin/bash
# accept_a_61740.sh — A 站 6.17.0-40 验收①: 内核/网络/显示
A="scott-lau@10.10.10.1"
echo "=== [1] USB4 可达性 ==="
ping -c 2 -W 2 10.10.10.1 | tail -1

echo "=== [2] 内核/主机名/接口 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "内核: $(uname -r)  主机: $(hostname)"
  echo "--- 网络接口 ---"
  ip -br addr | grep -vE "lo |docker|outline" | head -6
  echo "--- TB netdev 协商 (读 A 站侧) ---"
  cat /sys/class/net/thunderbolt0/speed 2>/dev/null || echo EINVAL已知怪癖
'

echo "=== [3] 显示 (xrandr 分辨率) ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  export DISPLAY=:0
  export XAUTHORITY=/run/user/$(id -u scott-lau)/gdm/Xauthority
  xrandr 2>/dev/null | grep -E "connected|current" | head -6 || echo "(无 X 权限, 用登录会话查)"
'

echo "=== [4] amdgpu/KFD 加载确认 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  lsmod | grep -E "^amdgpu|^thunderbolt" | head -3
  sudo dmesg | grep -iE "amdgpu.*(GTT|VRAM|Initialized)" | tail -4
'