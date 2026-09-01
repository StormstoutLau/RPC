#!/bin/bash
# b5f_token_write.sh — B5f 生成随机 token 写入 universal_tokens + 清理无 key 的手动 system 记录 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
echo "===== $(hostname -s) token write @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] 生成 32 位随机 token 并写入记录 l7f9k7px73 ---"
NEWTOKEN=$(openssl rand -hex 16)
curl -s -X PATCH "$HUB/api/collections/universal_tokens/records/l7f9k7px73" -H "$AH" \
  -H 'Content-Type: application/json' -d "{\"token\":\"${NEWTOKEN}\"}" | jq . 2>/dev/null

echo ""
echo "--- [2] 删除无 key 的手动 system 记录 (agent 自动注册将重建) ---"
for SID in ew3dw8eebk2kce1 3yceibjc4a35o0b; do
  curl -s -X DELETE "$HUB/api/collections/systems/records/${SID}" -H "$AH" -o /dev/null -w "delete ${SID}: %{http_code}\n"
done

echo ""
echo "--- [3] 复查 systems / universal_tokens 终态 ---"
curl -s "$HUB/api/collections/systems/records" -H "$AH" | jq -r 'totalItems: \(.totalItems), items: \([.items[]? | .id] | join(","))' 2>/dev/null
echo "UNIVERSAL_TOKEN=${NEWTOKEN}" | tee /tmp/b5f_token.txt
