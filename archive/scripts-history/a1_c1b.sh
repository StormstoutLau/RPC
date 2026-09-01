#!/bin/bash
# A1-C1b: 专家张量 -> RPC 端, 依次尝试 v0.2.0 可接受的设备名语法
# C1 首轮 'RPC0' 被拒(error: unrecognized buffer type), 候选: RPC / RPC0[addr] / RPC[addr]
set -x
LOGDIR=/home/scott-lau/llama-distributed/logs
TS=$(date +%Y%m%d_%H%M%S)
M=/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf
BIN=/opt/llama.cpp/llama-bench
OT='blk\.[0-9]+\.ffn_(up|down|gate)_exps'

sudo systemctl stop llama-server
sleep 2

for NAME in 'RPC' 'RPC0[10.10.10.1:50052]' 'RPC[10.10.10.1:50052]'; do
  LOG="$LOGDIR/bench_a1_c1b_exps_${TS}.log"
  echo "=== TRY: $NAME ==="
  timeout 900 $BIN -m "$M" --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -ot "$OT=$NAME" -p 512 -n 128 -r 2 > "$LOG" 2>&1
  RC=$?
  echo "TRY=$NAME rc=$RC"
  if grep -q 'unrecognized buffer' "$LOG"; then
    echo "ARG_REJECT=$NAME"
    continue
  fi
  echo "ACCEPTED=$NAME"
  break
done

sudo systemctl start llama-server
echo "C1B_DONE TS=$TS"
