#!/bin/bash
# A 站: opencode 现状 + mihomo 代理状态
set -u
echo "=== 1. opencode 版本/路径 ==="
/snap/bin/opencode --version 2>/dev/null || ls ~/.opencode/bin/opencode 2>/dev/null || echo "(opencode 不在已知路径)"
which opencode 2>/dev/null
echo "=== 2. 现有 opencode 配置 ==="
cat ~/.config/opencode/opencode.jsonc 2>/dev/null || echo "(无配置)"
echo "=== 3. mihomo 代理 ==="
ps aux | grep -iE 'mihomo|clash' | grep -v grep | head -2 || echo "(无代理进程)"
ss -tlnp 2>/dev/null | grep 7890 || echo "(7890 未监听)"
echo "=== 4. 代理连通性 ==="
timeout 5 curl -s -o /dev/null -w "models.dev via proxy: %{http_code}\n" -x http://127.0.0.1:7890 https://models.dev 2>/dev/null || echo "(代理不可用)"
echo DONE_A_OC
