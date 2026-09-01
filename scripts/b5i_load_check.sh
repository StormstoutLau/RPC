#!/bin/bash
# b5i_load_check.sh — 检查 llama-server 加载活性
PID=$(pgrep -f 'opt/llama.cpp/llama-server' | head -1)
echo "PID=$PID  $(grep -E '^State' /proc/$PID/status 2>/dev/null)"
top -b -n 2 -d 1 -p "$PID" | grep -E '^\s*'"$PID" | tail -2
echo "--- 累计 CPU 时间 ---"
ps -o pid,etime,time,stat,comm -p "$PID"
echo "--- A 站 rpc-server 活性 ---"
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local '
RPID=$(pgrep -f ggml-rpc-server | head -1)
ps -o pid,etime,time,stat -p "$RPID"
cat /proc/net/dev | grep -E "thunderbolt|en.*10" | head -2
' 2>/dev/null
echo "--- B 站最新日志 ---"
journalctl -u llama-server@m27-q4ks --no-pager -n 3 | tail -3
