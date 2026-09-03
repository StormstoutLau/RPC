#!/bin/bash
echo "== 底层 llama-server 进程 =="
ps -eo pid,etime,cmd | grep '[l]lama-server' | grep -v defunct | awk '{print "pid="$1" etime="$2" cmd="substr($0,index($0,"/home"))}' | head -c 800
echo
echo "== unsloth 是否能访问模型 (行为: opencode 报 server error 但 curl 正常 => unsloth 中间层对 opencode 请求处理失败) =="
echo "== 抓 unsloth studio server 日志 =="
ls -lt /home/scott-lau/.unsloth/studio/server/*.log /home/scott-lau/.unsloth/studio/logs/**/*.log 2>/dev/null | head -5
tail -30 /home/scott-lau/.unsloth/studio/server/*.log 2>/dev/null | tail -20