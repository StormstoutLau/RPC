#!/bin/bash
# bench_phase1.sh — Phase 1 验证 bench (pm_qos=100 + MTU9000 生效后)
# 参数与 Phase 0 基线完全一致: ngl=999 t=16 b=512 n-cpu-moe=8 fa=on, -p 512 -n 128 -r 2
set -uo pipefail
MODEL="/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf"
LOG="$HOME/llama-distributed/logs/bench_phase1_pm_qos_mtu_$(date +%Y%m%d_%H%M%S).log"
BIN=/opt/llama.cpp/llama-bench

nc -z 10.10.10.1 50052 2>/dev/null || { echo "FAIL: A 站 RPC 不可达"; exit 1; }

echo "=== Phase1 bench: pm_qos=100 + MTU9000, $(date) ===" | tee "$LOG"
echo "# 参数同基线: ngl=999 t=16 b=512 n-cpu-moe=8 fa=on r=2" | tee -a "$LOG"

"$BIN" -m "$MODEL" \
  --rpc 10.10.10.1:50052 \
  -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on \
  -p 512 -n 128 -r 2 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

echo "=== 完成 RC=$RC: $LOG ===" | tee -a "$LOG"
exit $RC
