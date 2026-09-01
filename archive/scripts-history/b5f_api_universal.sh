#!/bin/bash
# b5f_api_universal.sh — B5f 探 universal_tokens 集合并创建通用 token (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
echo "===== $(hostname -s) universal_tokens @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"

echo "--- [1] universal_tokens 现有记录 ---"
curl -s "$HUB/api/collections/universal_tokens/records" -H "$AH" | jq . 2>/dev/null | head -40

echo "--- [2] 尝试创建通用 token (有效期10年) ---"
# PocketBase 创建记录: token 字段通常自动生成
R=$(curl -s -X POST "$HUB/api/collections/universal_tokens/records" -H "$AH" \
  -H 'Content-Type: application/json' -d '{}')
echo "$R" | jq . 2>/dev/null | head -30

echo "--- [3] 若 [2] 失败, 试带字段名创建 ---"
if ! echo "$R" | jq -e '.id' >/dev/null 2>&1; then
  curl -s -X POST "$HUB/api/collections/universal_tokens/records" -H "$AH" \
    -H 'Content-Type: application/json' \
    -d '{"name":"cluster-agent","note":"RPC cluster A/B"}' | jq . 2>/dev/null | head -30
fi
