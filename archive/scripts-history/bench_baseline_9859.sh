#!/bin/bash
# bench_baseline_9859.sh — 9859 基线固化（B 站 Master, RPC 双机分布式）
# 用途: 升级 v0.2.0 前的性能基线（SOP 前置步骤）
set -uo pipefail
MODEL="/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf"
LOG="$HOME/llama-distributed/logs/bench_9859_$(date +%Y%m%d_%H%M%S).log"
BIN=/opt/llama.cpp/llama-bench

# 前置: A 站 RPC 可达
nc -z 10.10.10.1 50052 2>/dev/null || { echo "❌ A 站 RPC 不可达"; exit 1; }

echo "=== llama-bench 基线 (9859, RPC 双机, $(date)) ===" | tee "$LOG"
echo "# 参数: ngl=999 t=16 b=512 n-cpu-moe=8 fa=on (ctx 由 llama-bench 自动计算)" | tee -a "$LOG"
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
