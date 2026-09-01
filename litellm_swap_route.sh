#!/bin/bash
# litellm 换防路由部署: 备份 → 换 config → restart → 验证
set -u
exec 2>&1

CFG=/home/scott-lau/litellm/config.yaml

echo "=== 1. 备份原 config ==="
cp -a $CFG $CFG.bak.minimax-20260901
ls -la $CFG.bak.minimax-20260901

echo "=== 2. 部署新 config ==="
cp /tmp/litellm_config_20260901.yaml $CFG
grep -E "model_name|api_base" $CFG

echo "=== 3. restart litellm ==="
sudo systemctl restart litellm
sleep 6
systemctl is-active litellm || { echo "!! STARTUP FAIL — journal:"; sudo journalctl -u litellm -n 20 --no-pager; exit 1; }

echo "=== 4. 路由清单验证 (GET /v1/models, 带 key) ==="
KEY=$(grep master_key $CFG | awk '{print $2}')
curl -s http://127.0.0.1:4000/v1/models -H "Authorization: Bearer $KEY" | python3 -c '
import sys, json
d = json.load(sys.stdin)
ids = [m["id"] for m in d.get("data", [])]
print("routes:", ids)
assert "nemotron" in ids and "gpt-oss" in ids, "!! 新路由缺失"
assert not any("minimax" in i for i in ids), "!! minimax 残留"
print("ROUTE_OK")'
echo DONE_LITELM_SWAP
