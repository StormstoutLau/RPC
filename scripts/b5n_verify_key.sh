#!/bin/bash
# B5n 验证 v2: master_key 生效性 (key 从 general_settings 块读取)
KEY=$(grep 'master_key:' ~/litellm/config.yaml | head -1 | sed 's/.*master_key: //')
echo "KEY_PREFIX=${KEY:0:12}..."
# 等待 litellm 端口就绪 (最多 30s)
for i in $(seq 1 15); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${KEY}" http://127.0.0.1:4000/v1/models)
  [ "$CODE" != "000" ] && break
  sleep 2
done
echo "WITHAUTH= $CODE  (期望 200)"
echo "NOAUTH  = $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/v1/models)  (期望 401)"
echo "BADKEY  = $(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer sk-RPC-wrong' http://127.0.0.1:4000/v1/models)  (期望 401)"
