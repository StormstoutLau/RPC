#!/bin/bash
echo "== 端口监听 =="
ss -tlnp 2>/dev/null | grep -E ':8081|:8083|:49933|:53205' | head
echo "== 进程 =="
ps -eo pid,etime,rss,args | grep -E "unsloth studio run|llama-server" | grep -v grep | head
echo "== 最近 llama-server 日志 =="
LL=$(ls -t /home/scott-lau/.unsloth/studio/logs/llama-server/*.log 2>/dev/null | head -1)
echo "log=$LL"
tail -12 "$LL" | grep -iE "model loaded|load_model|error|failed|exited|KV cache|gguf|listening" | tail -8
echo "== 8083 是否就是 nemotron 服务（API） =="
curl -s -o /dev/null -w "8083=%{http_code}\n" http://127.0.0.1:8083/api/health 2>&1