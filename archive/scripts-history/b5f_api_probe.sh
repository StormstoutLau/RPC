#!/bin/bash
# b5f_api_probe.sh — B5f hub API 探测 (B 站): superuser 认证 + systems schema + 建 A/B system + 提取 agent KEY
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"

echo "===== $(hostname -s) API probe @ $(date '+%F %T') ====="

AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' \
  -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
[ -n "$TOKEN" ] || { echo "FATAL: superuser auth 失败: $(echo "$AUTH" | head -c 200)"; exit 1; }
echo "superuser token ✓"

echo "--- [1] systems 集合 schema ---"
curl -s "$HUB/api/collections/systems/records" -H "Authorization: ${TOKEN}" | jq . 2>/dev/null | head -40

echo "--- [2] users 集合 (admin 是否已自动建) ---"
curl -s "$HUB/api/collections/users/records" -H "Authorization: ${TOKEN}" | jq -r '.items[]? | "\(.id)  \(.email)  role=\(.role // "?")"' 2>/dev/null || echo "(空)"
