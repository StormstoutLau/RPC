#!/bin/bash
# check_beszel_alert.sh — 验证 A 站 Status 告警是否触发 (监控闭环检验)
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')
curl -s "$HUB/api/collections/alerts/records?perPage=10" -H "Authorization: $TOKEN" | \
  python3 -c '
import json,sys
for it in json.load(sys.stdin).get("items",[]):
    print(it["system"][:8], "|", it["name"], "| triggered =", it.get("triggered"))'