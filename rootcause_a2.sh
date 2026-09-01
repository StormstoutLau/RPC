#!/bin/bash
# rootcause_a2.sh — 经 B 站跳板抓 A 站上次启动日志 (黑屏根因)
echo "=== [1] A 站当前状态 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 \
  'echo HOST=$(hostname); uptime; systemctl is-active rpc-server@m27-q4ks' 2>&1 | head -5
echo
echo "=== [2] A 站上次启动 (-b -1) 尾部 (黑屏前最后记录) ==="
timeout 25 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 \
  'sudo journalctl -b -1 --no-pager | tail -25' 2>&1 | tail -28
echo
echo "=== [3] A 站上次启动 kernel 关键行 (amdgpu/GTT/OOM/hang) ==="
timeout 25 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 \
  'sudo journalctl -b -1 -k --no-pager | grep -iE "amdgpu|gtt|oom|out of memory|gpu hang|reset|panic|lockup|fault|killed|userptr|evict|workqueue" | tail -25' 2>&1 | tail -28
echo
echo "=== [4] A 站上次启动 rpc-server@m27 尾部 ==="
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 \
  'sudo journalctl -b -1 -u rpc-server@m27-q4ks --no-pager | tail -6' 2>&1 | tail -8