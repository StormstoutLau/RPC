#!/bin/bash
echo "== 8080 占用进程 =="
ss -tlnp 2>/dev/null | grep ":8080" | head
echo "== 底层 llama-server 进程 =="
ps -eo pid,etime,rss,cmd | grep "[l]lama-server" | grep -v defunct | awk '{printf "pid=%s etime=%s rss=%.1fG\n",$1,$2,$3/1048576}'
echo "== unsloth log 完整尾部 =="
tail -30 /home/scott-lau/.unsloth/run-gpt-oss-120b.log
echo "== studio logs llama-server 最近 =="
ls -t /home/scott-lau/.unsloth/studio/logs/llama-server/*.log 2>/dev/null | head -2