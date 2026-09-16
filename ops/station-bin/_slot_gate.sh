#!/bin/bash
# _slot_gate.sh - probe engine occupancy (O-25 P1 slot gate). Usage: bash _slot_gate.sh <port>
# 2026-09-16 (C2): 数据源由裸 llama-server 的 /slots 改为 unsloth studio 的
#   /api/inference/active-generations (固定 8080 引擎面)。依据:
#     ① C2 后引擎面统一为 studio 8080; 裸端口随机, 且**不反映经 8080 发起的生成**
#        (实测忙态下前 3 槽仍 is_processing=false)。
#     ② active-generations 直接给 count + parallel_slots, 比逐槽聚合更准。
#   输出契约**不变** (SLOT_TOTAL/SLOT_BUSY/SLOT_QUEUE) => Invoke-SlotGate 与 wrapper 无需改。
#   SLOT_BUSY = count (有生成在跑即忙, 与原 busy>0 -> exit 24 语义等价), SLOT_QUEUE = 0。
# NOTE: ASCII only (no non-ASCII comment) - avoids BOM/concat pitfalls inherited across scp/ssh.
set -uo pipefail
PORT="${1:-}"
[ -n "$PORT" ] || { echo "ERR_SLOT_PORT_NA"; exit 20; }
KEYF="$HOME/.config/rpc/unsloth.key"
K=""
[ -f "$KEYF" ] && K=$(tr -d '[:space:]' < "$KEYF" 2>/dev/null)
if [ -n "$K" ]; then
  BODY=$(curl -s -m4 -H "Authorization: Bearer $K" "http://127.0.0.1:$PORT/api/inference/active-generations" 2>/dev/null)
else
  BODY=$(curl -s -m4 "http://127.0.0.1:$PORT/api/inference/active-generations" 2>/dev/null)
fi
echo "$BODY" | grep -q '"parallel_slots"' || { echo "SLOT_NA (no active-generations; non-studio or old engine)"; exit 0; }
python3 - "$BODY" <<'PY'
import sys, json
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("SLOT_NA (parse failed)")
    sys.exit(0)
tot = int(d.get("parallel_slots") or 0)
busy = int(d.get("count") or 0)
print("SLOT_TOTAL=%d SLOT_BUSY=%d SLOT_QUEUE=%d" % (tot, busy, 0))
PY
