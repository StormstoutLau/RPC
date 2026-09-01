#!/bin/bash
# b5f_stats_check.sh — B5f 验证 system_stats 指标采集 (B 站)
set -uo pipefail
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
AUTH=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r '.token // empty')
AH="Authorization: ${TOKEN}"
echo "===== system_stats @ $(date '+%F %T') ====="
curl -s "$HUB/api/collections/system_stats/records?sort=-created&perPage=4" -H "$AH" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('total:', d.get('totalItems'))
for it in d.get('items', []):
    print(f\"  {it.get('system')}  {it.get('created')}  cpu={it.get('cpu')}  mem={it.get('memUsed')}/{it.get('memTotal')}  swap={it.get('swapUsed')}  disk={it.get('diskUsed')}\")
"
echo ""
echo "===== 主控站视角: hub Web 可达性 ====="
curl -s -o /dev/null -w "http://192.168.1.15:8090 -> %{http_code}\n" --max-time 5 http://192.168.1.15:8090/
