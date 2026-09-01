#!/bin/bash
# b5o_list_alerts.sh — 登录 Beszel hub, 列出现有告警 (看 schema)
HUB="http://127.0.0.1:8090"
USER="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"

TOKEN=$(curl -s "$HUB/api/beszel/collections/users/auth-with-password" \
  -H 'Content-Type: application/json' \
  -d "{\"identity\":\"$USER\",\"password\":\"$PASS\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')
echo "token_len=${#TOKEN}"

curl -s "$HUB/api/beszel/collections/alerts/records" \
  -H "Authorization: $TOKEN" | python3 -m json.tool 2>/dev/null | head -80