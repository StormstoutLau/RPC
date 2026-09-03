#!/bin/bash
echo "===== 日志尾部 ====="
tail -30 /home/scott-lau/.unsloth/run-nemotron-vulkan.log 2>/dev/null
echo "===== 端口监听 ====="
ss -tlnp 2>/dev/null | grep -E ':8084|:808' | head
echo "===== llama-server 进程（确认用的是 /opt vulkan） ====="
ps -eo pid,args | grep '[l]lama-server' | head