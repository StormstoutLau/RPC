#!/bin/bash
echo "== 当前 unsloth 进程 =="
ps -eo pid,etime,cmd | grep "[u]nsloth studio run" | awk '{print "pid="$1" etime="$2" cmd="substr($0,index($0,"gpt-oss"))}' | head
echo "== 端口 =="
ss -tln 2>/dev/null | grep -E ":808[0-9]|:809[0-9]" | awk '{print $4}'
echo "== 最近 unsloth log 就绪状态 =="
ls -t /home/scott-lau/.unsloth/run-gpt-oss-120b.log 2>/dev/null && grep -iE "running at|Model loaded|API Key|error|fail" /home/scott-lau/.unsloth/run-gpt-oss-120b.log | tail -5
echo "== 内存 =="
free -g | head -2