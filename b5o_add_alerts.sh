#!/bin/bash
# b5o_add_alerts.sh — 确认 system id 归属 + 加 CPU 告警 (两站)
HUB="http://127.0.0.1:8090"
TOKEN=$(curl -s -X POST "$HUB/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')

echo "=== systems 归属 ==="
curl -s "$HUB/api/collections/systems/records?perPage=10" -H "Authorization: $TOKEN" | \
  python3 -c '
import json,sys
for it in json.load(sys.stdin)["items"]:
    print(it["id"], "|", it.get("name",""), "|", it.get("host",""), "|", it.get("status",""))'

# CPU 告警: 两站各一条 (value=95% 持续 3min; 正常推理 CPU 不会全核打满,
# 挂死前兆 workqueue hogged 表现为持续高 CPU + 伴随指标恶化, 此为可用近似)
add_alert() {
  local SYSID=$1 NAME=$2
  RESP=$(curl -s -X POST "$HUB/api/collections/alerts/records" \
    -H "Authorization: $TOKEN" -H "Content-Type: application/json" \
    -d "{\"name\":\"$NAME\",\"value\":95,\"min\":3,\"system\":\"$SYSID\"}")
  echo "add[$NAME @ $SYSID]: $(echo $RESP | head -c 150)"
}
# 待归属确认后执行 — 先跑 systems 列表, 人工确认 id 再加