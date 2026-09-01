#!/bin/bash
# b5f_api_token_create.sh — B5f 创建 universal token (关联 admin user) (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
USERID="bb9i0ff4bor7420"
echo "===== $(hostname -s) universal token create @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] 创建 universal token ---"
R=$(curl -s -X POST "$HUB/api/collections/universal_tokens/records" -H "$AH" \
  -H 'Content-Type: application/json' -d "{\"user\":\"${USERID}\",\"name\":\"cluster-agent\"}")
echo "$R" | jq . 2>/dev/null

echo ""
echo "--- [2] 若失败, 不带 name 只带 user ---"
if ! echo "$R" | jq -e '.id' >/dev/null 2>&1; then
  curl -s -X POST "$HUB/api/collections/universal_tokens/records" -H "$AH" \
    -H 'Content-Type: application/json' -d "{\"user\":\"${USERID}\"}" | jq . 2>/dev/null
fi

echo ""
echo "--- [3] 复查全部 universal tokens ---"
curl -s "$HUB/api/collections/universal_tokens/records" -H "$AH" | jq -r '.items[]? | "\(.id)  token=\(.token // "?")  status=\(.status // "?")"' 2>/dev/null
