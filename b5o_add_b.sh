#!/bin/bash
# b5o_add_b.sh — 补 B 站 CPU 告警 + 清理试验记录
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')
USERID="bb9i0ff4bor7420"
B_ID="gqyb73pjkjd1lla"

echo "--- B 站 CPU ---"
curl -s -X POST "$HUB/api/collections/alerts/records" \
  -H "Authorization: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"CPU\",\"value\":95,\"min\":3,\"system\":\"$B_ID\",\"user\":\"$USERID\"}" | head -c 250; echo

echo "--- 清理 Temperature=99 试验记录 (A 站) ---"
curl -s -X DELETE "$HUB/api/collections/alerts/records?filter=(value=99)" -H "Authorization: $TOKEN" | head -c 100; echo
# 上面 filter 删不动就直接列 id 删
IDS=$(curl -s "$HUB/api/collections/alerts/records?filter=(value=99)" -H "Authorization: $TOKEN" | \
  python3 -c 'import json,sys; [print(i["id"]) for i in json.load(sys.stdin).get("items",[])]')
for i in $IDS; do
  curl -s -X DELETE "$HUB/api/collections/alerts/records/$i" -H "Authorization: $TOKEN" >/dev/null && echo "deleted $i"
done

echo "=== 终态: 全部告警 ==="
curl -s "$HUB/api/collections/alerts/records?perPage=20" -H "Authorization: $TOKEN" | \
  python3 -c '
import json,sys
for it in json.load(sys.stdin).get("items",[]):
    print(f"{it[\"system\"][:6]} | {it[\"name\"]:12} | {it[\"value\"]} | min={it[\"min\"]}")'