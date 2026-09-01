#!/bin/bash
# b5f_check_systems.sh — B5f 查 hub systems 注册状态 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"
echo "===== systems @ $(date '+%F %T') ====="
curl -s "$HUB/api/collections/systems/records" -H "$AH" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('total:', d.get('totalItems'))
for it in d.get('items', []):
    print(f\"  {it['id']}  {it.get('name')}  host={it.get('host')}  status={it.get('status')}  port={it.get('port')}\")
"
echo ""
echo "===== agent 进程状态 ====="
systemctl is-active beszel-agent
