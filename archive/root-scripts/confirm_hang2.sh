#!/bin/bash
# confirm_hang2.sh — 确认 A 站半挂死复发 + 压测残留状态
echo "=== [1] A 站新 TCP (ssh) ==="
timeout 12 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no scott-lau@10.10.10.1 'echo ALIVE' 2>&1 | head -2
echo
echo "=== [2] 生成是否仍在推进 (RPC 数据面) ==="
journalctl -u llama-server@m27-q4ks --since '3 minutes ago' --no-pager | grep 'n_gen' | tail -2
echo
echo "=== [3] 压测客户端/看门狗残留 ==="
ps aux | grep -E '[k]fd_stress|[k]fd_watchdog' | head -4 || echo "(均已退出)"
echo
echo "=== [4] B 站压测期间(03:17后) KFD 签名 ==="
journalctl -k --since "03:17" --no-pager | grep -iE "hogged|amdkfd" | tail -5 || echo "(B 站零 KFD 警告)"