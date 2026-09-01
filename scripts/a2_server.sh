#!/bin/bash
# A2: rpc-server GGML_RPC_DEBUG=1 采证窗口控制 (A 站)
# 用法: bash a2_server.sh start|truncate|stop
set -x
case "$1" in
start)
  sudo systemctl stop rpc-server
  sleep 2
  export LLAMA_CACHE=/data/rpccache/MiniMax-M2.7-Q4KS
  GGML_RPC_DEBUG=1 nohup /opt/llama.cpp/ggml-rpc-server -H 10.10.10.1 -p 50052 -c > /tmp/rpc_debug.log 2>&1 < /dev/null &
  for i in $(seq 1 60); do
    ss -tln | grep -q '10.10.10.1:50052' && { echo DEBUG_SERVER_READY; exit 0; }
    sleep 1
  done
  echo DEBUG_SERVER_TIMEOUT; exit 1
  ;;
truncate)
  : > /tmp/rpc_debug.log && echo LOG_TRUNCATED
  ;;
stop)
  pkill -f 'ggml-rpc-server -H 10.10.10.1'; sleep 2
  sudo systemctl start rpc-server; sleep 2
  systemctl is-active rpc-server
  ss -tln | grep 50052
  ;;
esac
