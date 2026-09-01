#!/bin/bash
# b5f_stats_full.sh — B5f 查 system_stats 完整字段 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"
curl -s "$HUB/api/collections/system_stats/records?sort=-created&perPage=1" -H "$AH" | jq '.items[0] // .'
