#!/bin/bash
echo "== 顶层内存 =="
free -g | head -2
echo "== 端口监听 =="
ss -tln 2>/dev/null | grep -E ':8080|:8085|:8086|:8087' | awk '{print $4}'
echo "== 现存 unsloth studio run 进程 =="
ps -eo pid,etime,rss,cmd | grep '[u]nsloth.studio.run' | awk '{printf "pid=%s etime=%s rss=%.1fG\n",$1,$2,$3/1048576}'
echo "== 现存活动 llama-server =="
ps -eo pid,etime,cmd | grep '[l]lama-server' | grep -v defunct | awk '{print "pid="$1" etime="$2" cmd="substr($0,index($0,$4))}'