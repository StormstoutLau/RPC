#!/bin/bash
# A3a: 应用低延迟套件后的 bench (B 站), 用法: bash a3a_bench.sh <tag>
set -x
LOGDIR=/home/scott-lau/llama-distributed/logs
TS=$(date +%Y%m%d_%H%M%S)
TAG=${1:-untagged}
M=/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf

sudo systemctl stop llama-server
sleep 2

/opt/llama.cpp/llama-bench -m "$M" --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2 > "$LOGDIR/bench_a3a_${TAG}_$TS.log" 2>&1
echo "A3A_BENCH_EXIT=$?"

grep -E 'pp512|tg128' "$LOGDIR/bench_a3a_${TAG}_$TS.log" || true

sudo systemctl start llama-server
sleep 3
systemctl is-active llama-server
echo "A3A_BENCH_DONE TAG=$TAG TS=$TS"
