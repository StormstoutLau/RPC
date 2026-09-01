#!/bin/bash
# bench_after_v020.sh — v0.2.0 升级后性能测试（与 9859 基线同参数）
set -uo pipefail
MODEL="/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf"
LOG="$HOME/llama-distributed/logs/bench_v020_$(date +%Y%m%d_%H%M%S).log"
BIN=/opt/llama.cpp/llama-bench

nc -z 10.10.10.1 50052 2>/dev/null || { echo "❌ A 站 RPC 不可达"; exit 1; }

echo "=== llama-bench v0.2.0 (RPC 双机, $(date)) ===" | tee "$LOG"
echo "# 同基线参数: ngl=999 t=16 b=512 n-cpu-moe=8 fa=on" | tee -a "$LOG"
"$BIN" --version 2>&1 | head -2 | tee -a "$LOG"
date +%s > /tmp/bench_start_ts

"$BIN" -m "$MODEL" \
  --rpc 10.10.10.1:50052 \
  -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on \
  -p 512 -n 128 -r 2 2>&1 | tee -a "$LOG"
RC=$?

END_TS=$(date +%s); START_TS=$(cat /tmp/bench_start_ts)
echo "" | tee -a "$LOG"
echo "=== 完成 (总耗时 $((END_TS-START_TS))s, RC=$RC): $LOG ===" | tee -a "$LOG"
exit $RC
