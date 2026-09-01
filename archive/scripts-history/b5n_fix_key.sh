#!/bin/bash
# B5n 修复: master_key 移入 general_settings (litellm 1.98.0 schema, 顶层字段被忽略)
set -e
CONF="$HOME/litellm/config.yaml"
KEY=$(grep '^master_key:' "$CONF" | head -1 | sed 's/master_key: //')

# 1. 删顶层行
sed -i '/^master_key:/d' "$CONF"

# 2. 插入 general_settings 块 (若无则创建, 若有则补 master_key 行)
if grep -q '^general_settings:' "$CONF"; then
  if grep -A20 '^general_settings:' "$CONF" | grep -q 'master_key:'; then
    echo "general_settings 内已有 master_key, 跳过"
  else
    sed -i "/^general_settings:/a\  master_key: ${KEY}" "$CONF"
    echo "已插入 general_settings.master_key"
  fi
else
  # 文件头追加块
  sed -i "1i general_settings:\n  master_key: ${KEY}" "$CONF"
  echo "已创建 general_settings 块 + master_key"
fi

echo "--- 预览 ---"
grep -B1 -A3 'master_key' "$CONF" | sed 's/\(master_key: sk-RPC-\).\{8\}.*/\1********/'

sudo systemctl restart litellm
sleep 6
echo "ACTIVE=$(systemctl is-active litellm)"
