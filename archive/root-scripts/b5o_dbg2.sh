#!/bin/bash
# b5o_dbg2.sh — Beszel 认证 (标准 PocketBase 路径 /api/collections)
HUB="http://127.0.0.1:8090"
RESP=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}')
TOKEN=$(echo "$RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("token",""))' 2>/dev/null)
echo "token_len=${#TOKEN}"
if [ -n "$TOKEN" ]; then
  echo "=== 现有告警 (schema 参考) ==="
  curl -s "$HUB/api/collections/alerts/records?perPage=20" -H "Authorization: $TOKEN" | python3 -m json.tool | head -70
fi