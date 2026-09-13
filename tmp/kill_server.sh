#!/bin/bash
# 停止当前 llama-server 并等待内存回落
pkill -x llama-server 2>/dev/null
sleep 5
pid=$(pgrep -x llama-server | head -1)
if [ -n "$pid" ]; then
  echo "SERVER-STILL-ALIVE pid=$pid, force kill"
  kill -9 "$pid"
  sleep 3
fi
pgrep -x llama-server >/dev/null && echo "ALIVE" || echo "DEAD"
free -g | head -2