#!/bin/bash
# b5f_api_setup.sh — B5f hub API 建 admin + 两 system 记录 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"

echo "===== $(hostname -s) API setup @ $(date '+%F %T') ====="
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
[ -n "$TOKEN" ] || { echo "FATAL: auth"; exit 1; }
AH="Authorization: ${TOKEN}"

echo "--- [1] 查/建 admin user (users 集合) ---"
U=$(curl -s "$HUB/api/collections/users/records?filter=email%3D%22${EMAIL}%22" -H "$AH")
USERID=$(echo "$U" | jq -r '.items[0].id // empty')
if [ -z "$USERID" ]; then
  U=$(curl -s -X POST "$HUB/api/collections/users/records" -H "$AH" -H 'Content-Type: application/json' \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASS}\",\"passwordConfirm\":\"${PASS}\",\"role\":\"admin\",\"name\":\"scott\",\"verified\":true}")
  USERID=$(echo "$U" | jq -r '.id // empty')
fi
echo "USERID=${USERID}"

echo "--- [2] 建 system A (NEX 192.168.1.11) ---"
A=$(curl -s -X POST "$HUB/api/collections/systems/records" -H "$AH" -H 'Content-Type: application/json' \
  -d "{\"name\":\"NEX-A\",\"host\":\"192.168.1.11\",\"port\":\"45876\",\"users\":[\"${USERID}\"]}")
echo "$A" | jq . | head -30

echo "--- [3] 建 system B (GTR-Pro 192.168.1.15) ---"
B=$(curl -s -X POST "$HUB/api/collections/systems/records" -H "$AH" -H 'Content-Type: application/json' \
  -d "{\"name\":\"GTR-B\",\"host\":\"127.0.0.1\",\"port\":\"45876\",\"users\":[\"${USERID}\"]}")
echo "$B" | jq . | head -30
