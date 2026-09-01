#!/bin/bash
# b5o_add_cpu.sh — 正式加 CPU 告警 (A/B 两站, 95% 持续 3min)
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')

A_ID="6qhew01z4lk7y0k"   # scott-lau-NEX
B_ID="gqyb73pjkjd1lla"   # scott-lau-GTR-Pro

add() {
  curl -s -X POST "$HUB/api/collections/alerts/records" \
    -H "Authorization: $TOKEN" -H "Content-Type: application/json" \
    -d "{\"name\":\"CPU\",\"value\":95,\"min\":3,\"system\":\"$1\"}" | head -c 200; echo
}
echo "--- A 站 CPU ---"; add "$A_ID"
echo "--- B 站 CPU ---"; add "$B_ID"
echo "=== 验证 (按 name=CPU 过滤) ==="
curl -s "$HUB/api/collections/alerts/records?filter=(name='CPU')" -H "Authorization: $TOKEN" | \
  python3 -c '
import json,sys
for it in json.load(sys.stdin).get("items",[]):
    print(it.get("system"), "CPU", it.get("value"), "% min", it.get("min"))'