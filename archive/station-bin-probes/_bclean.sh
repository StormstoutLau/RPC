#!/bin/bash
echo "== 清理所有 unsloth =="
pkill -9 -f "studio run" 2>/dev/null || true
pkill -9 -x llama-server 2>/dev/null || true
sleep 4
echo "== 残留 =="
ps -eo pid,etime,cmd | grep -E "studio run|llama-server" | grep -v defunct | grep -v grep | head || echo "(无)"
echo "== 内存 =="
free -g | head -2
echo "== 端口 =="
ss -tln 2>/dev/null | grep -E ":8080|:8081" | awk '{print $4}' || echo "(端口已释放)"