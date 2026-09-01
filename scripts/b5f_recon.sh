#!/bin/bash
# b5f_recon.sh — B5f Beszel 前置侦察 (B 站, 只读): 端口/依赖/GitHub 可达性/最新版本
set -u
echo "===== $(hostname -s) @ $(date '+%F %T') ====="

echo "--- [1] 端口 8090 (hub) / 45876 (agent) ---"
ss -tln | grep -E ':(8090|45876) ' || echo "8090/45876 空闲 ✓"

echo "--- [2] 依赖: unzip / jq ---"
command -v unzip >/dev/null && unzip -v | head -1 || echo "unzip 缺失"
command -v jq >/dev/null && jq --version || echo "jq 缺失 (用 python3 解析 JSON)"

echo "--- [3] GitHub API 可达性 + 最新 release ---"
R=$(curl -s --max-time 20 --retry 2 https://api.github.com/repos/henrygd/beszel/releases/latest)
if echo "$R" | grep -q tag_name; then
  echo "$R" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('tag:', d['tag_name'])
for a in d['assets']:
    if 'linux_amd64' in a['name'] and ('agent' in a['name']) != ('agent' in a['name'] and 'agent' not in a['name']):
        pass
for a in d['assets']:
    n=a['name']
    if 'linux_amd64' in n:
        print(f\"{n}  ({a['size']//1024}KB)  {a['browser_download_url']}\")
"
else
  echo "GitHub API 直连失败, 前 200 字: $(echo "$R" | head -c 200)"
  echo "--- ghproxy 兜底探测 ---"
  curl -s --max-time 20 -o /dev/null -w 'ghproxy.net: %{http_code}\n' "https://ghproxy.net/https://raw.githubusercontent.com/henrygd/beszel/main/README.md" || true
fi

echo "--- [4] 磁盘 ---"
df -h / | tail -1
