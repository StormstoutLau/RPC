#!/bin/bash
# b5f_api_pubkey.sh — B5f 从 hub 获取全局公钥 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
echo "===== $(hostname -s) hub pubkey probe @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] PocketBase settings (找 key 相关字段) ---"
curl -s "$HUB/api/settings" -H "$AH" | jq '.' 2>/dev/null | grep -iE 'key|ed25519|ssh|beszel' | head -20

echo "--- [2] settings 全 dump 前 60 行 ---"
curl -s "$HUB/api/settings" -H "$AH" | jq '.' 2>/dev/null | head -60

echo "--- [3] 试 hub 内部端点 /api/beszel/... ---"
for EP in /api/beszel/key /api/beszel/public-key /api/beszel/pubkey; do
  CODE=$(curl -s -o /tmp/b5f_ep.out -w "%{http_code}" "$HUB$EP" -H "$AH")
  echo "GET $EP -> $CODE"
  [ "$CODE" != "404" ] && head -c 300 /tmp/b5f_ep.out && echo ""
done
