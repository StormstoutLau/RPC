#!/bin/bash
echo "== A站 /data/models/gguf 顶层 =="
ls -la /data/models/gguf 2>/dev/null
echo "== A站 全盘找 nemotron gguf =="
find /data/models /home/scott-lau -maxdepth 6 -iname "*nemotron*" 2>/dev/null | head
echo "== A站 当前模型相关进程 =="
ps -eo pid,etime,rss,cmd | grep -E "unsloth|llama-server" | grep -v grep | head
echo "== A站 8081 是否还活着 =="
curl -s -o /dev/null -w "health8081=%{http_code}\n" http://127.0.0.1:8081/api/health 2>&1
echo "== A站 磁盘空间 =="
df -h /data 2>/dev/null | tail -1