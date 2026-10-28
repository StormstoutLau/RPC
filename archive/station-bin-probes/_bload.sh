#!/bin/bash
echo "== B 当前加载的模型 (llama-server) =="
ps -eo pid,args | grep llama-server | grep -v grep | grep -oE "\-m [^ ]+|\-\-port [0-9]+|\-ngl [0-9]+" | head -30
echo "== 按进程分列 =="
ps -eo pid,etime,args | grep "[l]lama-server" | sed 's/--port/port=/' | head
echo "== 8080 健康 =="
curl -s -o /dev/null -w "8080=%{http_code}\n" http://127.0.0.1:8080/health 2>&1
echo "== mem =="
free -g | head -2