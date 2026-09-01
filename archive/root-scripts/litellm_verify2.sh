#!/bin/bash
# litellm 路由验证 v2: journal 检查 + 正确取 key + models + E2E
set -u
exec 2>&1

echo "=== 1. litellm journal (启动后有无错误) ==="
sudo journalctl -u litellm --since '-5 min' --no-pager | grep -iE 'error|fail|exception|traceback' | tail -6 || echo "(无错误日志)"

echo "=== 2. 取 key 并验证 /v1/models ==="
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')
echo "key 长度: ${#KEY}"
RESP=$(curl -s -w '\n%{http_code}' http://127.0.0.1:4000/v1/models -H "Authorization: Bearer $KEY")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
echo "HTTP=$CODE"
echo "$BODY" | head -c 400
echo ""
if [ "$CODE" = "200" ]; then
  echo "$BODY" | python3 -c '
import sys, json
d = json.load(sys.stdin)
ids = [m["id"] for m in d.get("data", [])]
print("routes:", ids)'
fi

echo "=== 3. 8080 后端当前状态 ==="
curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && echo "8080 READY (有模型加载)" || echo "8080 无模型 (集群干净态, E2E 测试需先 infer-load)"
echo DONE_V2
