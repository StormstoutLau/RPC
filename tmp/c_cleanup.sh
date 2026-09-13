#!/bin/bash
# C 站清理 + B 站对照服务状态确认
set +e
echo "=== C 站清理 ==="
pkill -9 -f llama-server 2>/dev/null
sleep 2
pgrep -af llama-server || echo '(C 无 llama-server 残留)'
ss -tlnp 2>/dev/null | grep -E '1808[1-4]' || echo '(18081-18084 已释放)'
free -g | head -2