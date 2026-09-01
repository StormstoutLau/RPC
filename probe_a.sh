#!/bin/bash
# probe_a.sh — 从 B 站探测 A 站 (新 TCP 连接 + 系统状态)
echo "=== [1] A 站新 TCP 连接测试 (USB4, ssh) ==="
timeout 20 ssh -o ConnectTimeout=12 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 \
  'echo CONNECTED: $(hostname); uptime; grep -E "MemAvailable" /proc/meminfo; echo ---dmesg---; sudo dmesg -T 2>/dev/null | tail -8' 2>&1 | head -20
echo "=== [2] exit=$? (0=连上, 124=超时) ==="