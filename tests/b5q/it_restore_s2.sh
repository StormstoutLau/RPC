#!/bin/bash
# B5q §3 判定执行 (撤销) + §2 生产恢复兼哨兵集成验证
set -uo pipefail
A="10.10.10.1"

echo '--- §3 判定: Δpp512=-4.9% (<-2%) → 撤销 drop-in ---'
ssh "$A" 'sudo rm /etc/systemd/system/rpc-server@.service.d/hostmem.conf && sudo systemctl daemon-reload && echo removed'
ssh "$A" 'sudo systemctl show rpc-server@m27-q4ks -p Environment'

echo '--- §2/恢复: infer-load m27 (生成 RPC_TARGET=auto conf + 启动) ---'
infer-load m27-q4ks 2>&1 | tail -15
sleep 5

echo '--- §2.2 验证: auto conf + 实际命令行展开 ---'
grep 'RPC_TARGET' /etc/llama-instances/m27-q4ks.env
echo 'llama-server 实际命令行 (--rpc 应为 10.10.10.1:50052):'
pgrep -af 'llama-server.*m27' | head -1
ps -eo args | grep 'llama-server' | grep -v grep | head -1

echo '--- 生产恢复验证 ---'
echo "B llama-server@m27-q4ks: $(systemctl is-active llama-server@m27-q4ks)"
echo "A rpc-server@m27-q4ks: $(ssh $A 'systemctl is-active rpc-server@m27-q4ks')"
