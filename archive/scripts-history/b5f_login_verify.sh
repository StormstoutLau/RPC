#!/bin/bash
# b5f_login_verify.sh — 验证 superuser 密码登录 (B 站)
HUB="http://127.0.0.1:8090"
EMAIL="peng.liu.john@gmail.com"
PASS="Beszel-49dc2e75"
R=$(curl -s -X POST "$HUB/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' \
  -d "{\"identity\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
if echo "$R" | grep -q '"token"'; then
  echo "LOGIN OK — 密码有效"
else
  echo "LOGIN FAIL: $(echo "$R" | head -c 200)"
fi
