#!/bin/bash
# A1: -ot MoE 张量放置试验 (2026-08-28, 调研报告行动项 A1)
# C0 基线 | C1 专家全->RPC0(A站) | C2 专家全->Vulkan0(B站) | C3 注意力全->Vulkan0(B站)
# 张量名已从 GGUF header 实测: ffn_(up|down|gate)_exps, attn_(k|q|v|output|norm|k_norm|q_norm)
set -x
LOGDIR=/home/scott-lau/llama-distributed/logs
TS=$(date +%Y%m%d_%H%M%S)
M=/home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf
BIN=/opt/llama.cpp/llama-bench
COMMON="--rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on"
OT_EXPS='blk\.[0-9]+\.ffn_(up|down|gate)_exps'
OT_ATTN='blk\.[0-9]+\.attn_[a-z_]+'

sudo systemctl stop llama-server
sleep 2

$BIN -m "$M" $COMMON -p 512 -n 128 -r 2 > "$LOGDIR/bench_a1_c0_baseline_$TS.log" 2>&1
echo "C0_EXIT=$?"
$BIN -m "$M" $COMMON -ot "$OT_EXPS=RPC0" -p 512 -n 128 -r 2 > "$LOGDIR/bench_a1_c1_exps_rpc0_$TS.log" 2>&1
echo "C1_EXIT=$?"
$BIN -m "$M" $COMMON -ot "$OT_EXPS=Vulkan0" -p 512 -n 128 -r 2 > "$LOGDIR/bench_a1_c2_exps_vulkan0_$TS.log" 2>&1
echo "C2_EXIT=$?"
$BIN -m "$M" $COMMON -ot "$OT_ATTN=Vulkan0" -p 512 -n 128 -r 2 > "$LOGDIR/bench_a1_c3_attn_vulkan0_$TS.log" 2>&1
echo "C3_EXIT=$?"

sudo systemctl start llama-server
echo "A1_DONE TS=$TS"
