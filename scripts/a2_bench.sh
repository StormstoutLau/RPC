#!/bin/bash
# A2: 短程 bench 触发 RPC 流量, 供 A 站 debug 日志采证 (B 站)
# 先由 A 站执行 a2_server.sh truncate 清空日志窗口
set -x
LOGDIR=/home/scott-lau/llama-distributed/logs
TS=$(date +%Y%m%d_%H%M%S)
M=/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf

sudo systemctl stop llama-server
sleep 2
/opt/llama.cpp/llama-bench -m "$M" --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 128 -n 128 -r 1 > "$LOGDIR/bench_a2_debug_$TS.log" 2>&1
echo "A2_EXIT=$?"
sudo systemctl start llama-server
echo "A2_DONE TS=$TS"
