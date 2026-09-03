#!/bin/bash
echo "== 8080 占用进程 =="
ss -tlnp 2>/dev/null | grep ":8080" | head
echo "== ssh/ps owner =="
ps -eo pid,etime,cmd | grep -E "unsloth|llama-server" | grep -v defunct | grep -v grep | head
echo "== 20b 实际端口 (8081) 健康 =="
curl -sf --max-time 5 http://127.0.0.1:8081/v1/models >/dev/null 2>&1 && echo "8081 OK" || echo "8081 no model yet"
curl -s --max-time 8 http://127.0.0.1:8081/v1/models -H "Authorization: Bearer ***REMOVED***" 2>&1 | head -c 200