#!/bin/bash
# b5f_api_tokens.sh — B5f 探 collections 列表 + 通用 token 路径 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
echo "===== $(hostname -s) tokens probe @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] collections 全列表 ---"
curl -s "$HUB/api/collections" -H "$AH" | jq -r '.items[]? | "\(.name)  \(.type // "?")"' 2>/dev/null | head -30

echo "--- [2] tokens 集合 schema (若存在) ---"
curl -s "$HUB/api/collections/tokens/records" -H "$AH" | jq . 2>/dev/null | head -25 || echo "tokens 集合不存在或不可读"

echo "--- [3] system A 单条完整字段 (看有无隐藏 key 字段) ---"
curl -s "$HUB/api/collections/systems/records/ew3dw8eebk2kce1" -H "$AH" | jq 'keys'
