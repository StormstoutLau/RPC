#!/bin/bash
echo "== A 上 qwen 3.8 27B 相关模型 =="
find /data/models -maxdepth 5 -iname "*.gguf" 2>/dev/null | grep -i "qwen3.8" | head
find /data/models -maxdepth 5 -iname "*.gguf" -exec ls -lh {} \; 2>/dev/null | awk '$9 ~ /qwen/i {print $5, $9}' | head
echo "== 当前 gpt-oss 加载后内存 =="
free -g | head -2
echo "== gpt-oss 进程 RSS =="
ps -eo rss,args | grep "[l]lama-server" | grep gpt-oss | awk '{printf "%.1f GB  %s\n",$1/1048576,$2}'