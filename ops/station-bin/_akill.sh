#!/bin/bash
echo "== 现存 llama-server =="
ps -eo pid,rss,args | grep '[l]lama-server' | awk '{printf "pid=%s rss=%.1fGB %s\n",$1,$2/1048576,$3}'
pkill -9 -x llama-server 2>/dev/null
sleep 4
echo "== 清理后 mem =="
free -g | head -2
echo "== 确认无残留 =="
ps -eo pid,args | grep '[l]lama-server' | head || echo "(无)"