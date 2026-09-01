#!/bin/bash
# B 站: opencode 现状 + 代理状态 + litellm 可达性
set -u
echo "=== 1. opencode 版本/路径 ==="
which opencode 2>/dev/null; ls ~/.opencode/bin/opencode 2>/dev/null && ~/.opencode/bin/opencode --version 2>/dev/null
echo "=== 2. 现有 opencode 配置 ==="
cat ~/.config/opencode/opencode.jsonc 2>/dev/null || echo "(无配置)"
echo "=== 3. 代理状态 (B 站) ==="
ps aux | grep -iE 'mihomo|clash' | grep -v grep || echo "(无代理进程 — 符合旧档结论)"
echo "=== 4. litellm :4000 存活 ==="
systemctl is-active litellm
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')
curl -s http://127.0.0.1:4000/v1/models -H "Authorization: Bearer $KEY" | head -c 200
echo; echo DONE_B_OC
