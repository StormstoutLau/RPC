#!/bin/bash
# rootcause_a.sh — A 站上次启动日志根因排查 (黑屏时刻 ~00:38-00:44)
echo "=== [1] 当前启动基本信息 ==="
uptime; hostnamectl | head -3
echo
echo "=== [2] 上次启动 (-b -1) 尾部日志 (黑屏前最后记录) ==="
sudo journalctl -b -1 --no-pager | tail -40
echo
echo "=== [3] 上次启动的 amdgpu/GTT/OOM/panic 关键行 ==="
sudo journalctl -b -1 --no-pager -k | grep -iE 'amdgpu|gtt|oom|out of memory|gpu hang|reset|panic|lockup|fault|killed' | tail -25
echo
echo "=== [4] 上次启动的 rpc-server 尾部 ==="
sudo journalctl -b -1 -u rpc-server@m27-q4ks --no-pager | tail -8
echo
echo "=== [5] 本次启动 (-b 0) amdgpu 状态 ==="
sudo journalctl -b 0 --no-pager -k | grep -iE 'amdgpu|thunderbolt|usb4' | head -12