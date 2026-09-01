#!/bin/bash
# b5o_dbg.sh — 逐步调试 Beszel 认证
HUB="http://127.0.0.1:8090"
RESP=$(curl -s -w '\nHTTP_CODE=%{http_code}\n' -X POST "$HUB/api/beszel/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}')
echo "AUTH RESP: $RESP" | head -c 500
echo
# 尝试另一已知账号变体 (b5f 部署用 peng)
RESP2=$(curl -s -w '\nHTTP_CODE=%{http_code}\n' -X POST "$HUB/api/beszel/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"peng","password":"Beszel-49dc2e75"}')
echo "AUTH2 RESP: $RESP2" | head -c 300