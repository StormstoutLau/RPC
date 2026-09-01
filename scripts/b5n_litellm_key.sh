#!/bin/bash
# B5n: litellm master_key 加固 (幂等)
# 用法: bash b5n_litellm_key.sh <key文件>  (本地传参避免 key 出现在 ps/历史)
set -e
KEY=$(cat "$1")
CONF="$HOME/litellm/config.yaml"

# 幂等: 已存在则替换
if grep -q '^master_key:' "$CONF"; then
  sed -i "s|^master_key:.*|master_key: ${KEY}|" "$CONF"
  echo "master_key 已更新 (替换)"
else
  # 插到文件头部 (顶层字段, 非 router_settings/general_settings 内)
  sed -i "1i master_key: ${KEY}" "$CONF"
  echo "master_key 已新增 (顶部)"
fi

echo "--- config 头部预览 ---"
head -3 "$CONF" | sed 's/\(master_key: sk-RPC-\).\{8\}.*/\1********/'

sudo systemctl restart litellm
sleep 5
systemctl is-active litellm

echo "--- 验证 1: 无 key 应 401 ---"
NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/v1/models)
echo "无 key HTTP $NOAUTH (期望 401)"

echo "--- 验证 2: 带 key 应通过认证 (后端未载模型时为 5xx 路由错误, 非 401 即认证通过) ---"
WITHAUTH=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${KEY}" http://127.0.0.1:4000/v1/models)
echo "带 key HTTP $WITHAUTH (期望非 401, 200 = 列出模型)"
