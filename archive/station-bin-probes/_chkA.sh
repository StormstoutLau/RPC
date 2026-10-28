#!/bin/bash
echo "== 运行中的相关进程 =="
ps -eo pid,etime,rss,cmd | grep -E "studio run|llama-server|uvicorn" | grep -v grep | head -20
echo "== 8081 是否可连 =="
curl -s -o /dev/null -w "health=%{http_code}\n" http://127.0.0.1:8081/api/health 2>&1
echo "== 底层 llama-server 最近日志（模型加载结果） =="
LL=$(ls -t /home/scott-lau/.unsloth/studio/logs/llama-server/*.log 2>/dev/null | head -1)
echo "logfile=$LL"
tail -30 "$LL" 2>/dev/null | grep -iE "model loaded|load_model|error|failed|KV cache|gguf|success|slot|server is listening" | tail -15
echo "== 端口占用 =="
ss -tlnp 2>/dev/null | grep -E ':8081|:49933' | head