#!/bin/bash
# b5f_mem_check.sh — B 站内存占用构成分析
echo "===== $(hostname -s) 内存构成 @ $(date '+%F %T') ====="
echo "--- [1] free ---"
free -h
echo ""
echo "--- [2] 关键指标 (MemTotal/Available/Cached/Anon) ---"
grep -E '^(MemTotal|MemFree|MemAvailable|Cached|AnonPages|Buffers|SReclaimable|Shmem):' /proc/meminfo
echo ""
echo "--- [3] 内存占用 TOP6 进程 (RSS) ---"
ps aux --sort=-rss | head -8 | awk '{printf "%-10s %8.1fGB  %s\n", $1, $6/1048576, substr($0, index($0,$11), 80)}'
echo ""
echo "--- [4] llama-server mmap 模型文件 ---"
PID=$(pgrep -f 'llama-serve[r]' | head -1)
if [ -n "$PID" ]; then
  echo "PID=${PID}, VmRSS: $(grep VmRSS /proc/$PID/status)"
  echo "mmap 文件:"
  sudo ls -la /proc/$PID/map_files 2>/dev/null | grep -oE '/[^ ]+\.gguf' | sort -u | head -5
fi
echo ""
echo "--- [5] 大文件页缓存量 (cachestat) ---"
sudo cat /proc/vmstat | grep -E '^(nr_pagecache_pages|nr_file_pages|nr_anon_pages):' || true
