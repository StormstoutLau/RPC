#!/bin/bash
# b5f_api_schema.sh — B5f 查看 universal_tokens schema + 尝试生成 token (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
echo "===== $(hostname -s) universal_tokens schema @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] universal_tokens 字段 schema ---"
curl -s "$HUB/api/collections/universal_tokens" -H "$AH" | jq '.fields // .schema // .' 2>/dev/null | head -60

echo ""
echo "--- [2] 尝试 PATCH 生成 token (重触发) ---"
curl -s -X PATCH "$HUB/api/collections/universal_tokens/records/ruqyjfr05e" -H "$AH" \
  -H 'Content-Type: application/json' -d '{}' | jq . 2>/dev/null

echo ""
echo "--- [3] 删除后重建看是否返回 token ---"
curl -s -X DELETE "$HUB/api/collections/universal_tokens/records/ruqyjfr05e" -H "$AH" -o /dev/null -w "deleted: %{http_code}\n"
R=$(curl -s -X POST "$HUB/api/collections/universal_tokens/records" -H "$AH" \
  -H 'Content-Type: application/json' -d '{"user":"bb9i0ff4bor7420"}')
echo "$R" | jq . 2>/dev/null
