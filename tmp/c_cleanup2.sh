#!/bin/bash
# C 站清理 + 确认
set +e
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
sleep 2
echo '=== 18081 ==='
ss -tlnp 2>/dev/null | grep 18081 || echo '(freed)'
echo '=== gpt 进程 ==='
ps aux | grep gpt-oss | grep -v grep || echo '(none)'
echo '=== qwen 18080 保留 ==='
ss -tlnp 2>/dev/null | grep 18080 | head -1 || echo '(qwen gone?)'
echo '=== 内存 ==='
free -g | head -2