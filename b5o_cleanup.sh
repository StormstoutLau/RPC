#!/bin/bash
# b5o_cleanup.sh — 删 Temperature=99 试验记录 + 终态列表
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')

python3 - "$TOKEN" <<'PYEOF'
import json, sys, urllib.request
TOKEN = sys.argv[1]
HUB = "http://127.0.0.1:8090"

def req(method, path, data=None):
    r = urllib.request.Request(HUB + path, method=method,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Authorization": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())

# 删 Temperature=99 试验记录
items = req("GET", "/api/collections/alerts/records?filter=(value=99)").get("items", [])
for it in items:
    req("DELETE", f"/api/collections/alerts/records/{it['id']}")
    print("deleted", it["id"], it["name"], it["value"])

# 终态
print("=== 终态告警清单 ===")
for it in req("GET", "/api/collections/alerts/records?perPage=30").get("items", []):
    print(it["system"][:8], "|", it["name"], "|", it["value"], "| min =", it["min"])
PYEOF