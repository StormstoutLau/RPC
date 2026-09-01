#!/bin/bash
# forensic_a.sh — A 站: 枚举 boots + 拉挂死 boot 完整证据
A="scott-lau@10.10.10.1"
echo "=== [0] A 站可达 + 当前内核 ==="
ping -c 2 -W 2 10.10.10.1 | tail -1
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A 'echo "内核: $(uname -r); host: $(hostname); uptime: $(uptime -p)"'

echo
echo "=== [1] boot 枚举 (找挂死 boot) ==="
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A 'sudo journalctl --list-boots --no-pager | tail -8'

echo
echo "=== [2] 挂死 boot (= -b -1) 的关键签名全 grep ==="
timeout 25 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "--- amdgpu/kfd/workqueue/PCI 异常 ---"
  sudo journalctl -b -1 -k --no-pager 2>/dev/null | grep -iE "hogged|amdkfd|kfd|gpu hang|reset|lockup|fault|oops|bug|panic|call trace|hardware error|aer|pcieport" | tail -25
  echo "--- 挂死前最后 15 行 (全 journal) ---"
  sudo journalctl -b -1 --no-pager 2>/dev/null | tail -15 | cut -c1-140
'

echo
echo "=== [3] A 站 /var/crash (有无本机转储) ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A 'ls -lt /var/crash/ 2>/dev/null | head -4; echo "(空则无)"'