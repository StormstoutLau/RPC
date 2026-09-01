#!/bin/bash
# b5_bench_cluster.sh — B5q-2: 一键全集群基准 (spec/cluster-bench DESIGN §4)
# 流程: 读 conf → rpc-nodes --start → llama-bench 冻结口径 → 自动收尾 → 输出 metrics 条目
# 用法: b5_bench_cluster.sh --alias m27-q4ks [--pp 512] [--tn 128] [-r 2] [--keep]
# 测试缝隙: CONF_DIR / RPC_HELPER / BENCH_BIN / LOG_DIR (tests/b5q/test_bench_cluster.sh)
set -uo pipefail

ALIAS=""; PP=512; TN=128; REPS=2; KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --alias) ALIAS="$2"; shift 2 ;;
    --pp)    PP="$2"; shift 2 ;;
    --tn)    TN="$2"; shift 2 ;;
    -r)      REPS="$2"; shift 2 ;;
    --keep)  KEEP=1; shift ;;
    *) echo "FATAL: 未知参数: $1" >&2; exit 3 ;;
  esac
done
[ -n "$ALIAS" ] || { echo "FATAL: 需要 --alias <alias>" >&2; exit 3; }

CONF_DIR="${CONF_DIR:-/etc/llama-instances}"
RPC_HELPER="${RPC_HELPER:-rpc-nodes}"
BENCH_BIN="${BENCH_BIN:-/opt/llama.cpp/llama-bench}"
LOG_DIR="${LOG_DIR:-/tmp}"

# 1. conf 读取 — 集群自动化要求确定性: 不存在即报错, 不做模糊 find (DESIGN §4)
CONF="${CONF_DIR}/${ALIAS}.env"
[ -f "$CONF" ] || { echo "FATAL: conf 不存在: $CONF (b5_bench_cluster 不做模糊 find)" >&2; exit 3; }
source "$CONF"
[ -n "${MODEL_PATH:-}" ] || { echo "FATAL: conf 缺 MODEL_PATH: $CONF" >&2; exit 3; }

cleanup() { # 自动收尾 (beowulf "Ensure stopped" 等价; 只 systemctl stop, 不 pkill — A3a 教训)
  [ "$KEEP" = "1" ] && return 0
  "$RPC_HELPER" --stop "$ALIAS" >/dev/null 2>&1 || true
}

# 2. RPC 列表 = rpc-nodes --start (起各节点 rpc-server + 等端口)
RPC_LIST="$("$RPC_HELPER" --start "$ALIAS" 2>/dev/null)" || RPC_LIST=""
if [ -z "$RPC_LIST" ]; then
  echo "FATAL: RPC 节点不可达 (rpc-nodes --start ${ALIAS} 失败), abort" >&2
  cleanup
  exit 4
fi
echo "[bench-cluster] rpc=${RPC_LIST}"

# 3. llama-bench 冻结口径 (DESIGN §2.8, 与 139.19 基线同参 — 勿改)
LOG="${LOG_DIR}/bench_cluster_${ALIAS}_$(date +%s).log"
"$BENCH_BIN" -m "$MODEL_PATH" --rpc "$RPC_LIST" \
  -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p "$PP" -n "$TN" -r "$REPS" 2>&1 | tee "$LOG"
BENCH_RC="${PIPESTATUS[0]}"

# 4. 自动收尾
cleanup
[ "$BENCH_RC" -ne 0 ] && { echo "FATAL: llama-bench 退出码 ${BENCH_RC}" >&2; exit 5; }

# 5. metrics 条目 (追加至 d:\RPC\spec\rpc-optimization\metrics-log.md — Phase 5)
echo "[metrics] Phase 5 | $(date '+%F %T') | cluster-bench | alias=${ALIAS} | rpc=${RPC_LIST} | pp${PP}/tn${TN} r${REPS} | 口径: -ngl999 -t16 -b512 --n-cpu-moe8 -fa on -p${PP} -n${TN} -r${REPS} | log=${LOG}"
exit 0
