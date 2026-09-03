#!/bin/bash
echo "== 现存 llama-server 进程 =="
ps -eo pid,etime,rss,args | grep llama-server | grep -v grep
echo "== top 内存占用 (前 8) =="
ps -eo pid,pmem,rss,comm --sort=-rss | head -9
echo "== free =="
free -g | head -2