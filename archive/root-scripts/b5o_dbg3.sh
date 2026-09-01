#!/bin/bash
# b5o_dbg3.sh — 400 详细报错 + 尝试带 user 字段
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')
USERID="bb9i0ff4bor7420"
A_ID="6qhew01z4lk7y0k"

echo "=== 尝试1: 带 user ==="
curl -s -X POST "$HUB/api/collections/alerts/records" \
  -H "Authorization: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"CPU\",\"value\":95,\"min\":3,\"system\":\"$A_ID\",\"user\":\"$USERID\"}" | head -c 300; echo
echo "=== 尝试2: name 用已存在的合法值 Temperature 验证 schema ==="
curl -s -X POST "$HUB/api/collections/alerts/records" \
  -H "Authorization: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Temperature\",\"value\":99,\"min\":3,\"system\":\"$A_ID\",\"user\":\"$USERID\"}" | head -c 300; echo