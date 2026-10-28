#!/bin/bash
# _reload_ctx.sh — O-21 确定性修复：把 A 站 gpt-oss 服务端上下文 65536 -> 131072 并重载
# 顺序: 备份conf -> sed CTX -> infer-load 重载(内部停旧+GTT释放+重启) -> 校验
set -uo pipefail
CONF=/etc/llama-instances/gpt-oss-120b.env
NEWCTX=131072
LOG=/home/scott-lau/.infer-reload.ctx.log

[ -f "$CONF" ] || { echo "ERR: no conf $CONF"; exit 1; }
# 备份 (硬规则: 破坏性操作前备份)
[ -f "${CONF}.bak-ctx65536" ] || sudo cp "$CONF" "${CONF}.bak-ctx65536"
echo "backup: $(sudo cat "${CONF}.bak-ctx65536" | grep -E '^CTX=')"

# 改 CTX
sudo sed -i "s/^CTX=.*/CTX=$NEWCTX/" "$CONF"
echo "conf after: $(grep -E '^CTX=' "$CONF")"

# 重载 (infer-load 内部 pkill 旧引擎 + wait_gtt + unsloth 重启) — 后台, 避免握手超时
echo "reloading (log=$LOG)..."
nohup bash /home/scott-lau/infer-load.new gpt-oss > "$LOG" 2>&1 &
echo "infer-load pid=$!"

# 轮询 READY (最多 ~8min: 停旧 + GTT 释放 + 120B 重新加载)
for i in $(seq 1 160); do
  if grep -q "READY ✓" "$LOG" 2>/dev/null; then
    echo "RELOAD_READY after ${i} polls"
    break
  fi
  if grep -qiE "^ERROR|ERROR:" "$LOG" 2>/dev/null; then
    echo "RELOAD_ERROR: $(grep -iE 'ERROR' "$LOG" | tail -3)"; exit 2
  fi
  sleep 3
done
grep -q "READY ✓" "$LOG" || { echo "RELOAD_TIMEOUT; tail:"; tail -20 "$LOG"; exit 3; }

# 校验: 新引擎端口 + /props 运行时 n_ctx
PORT=""
for p in $(ss -tlnp 2>/dev/null | grep 'llama-server' | grep -oE '127\.0\.0\.1:[0-9]+' | cut -d: -f2 | sort -un); do
  M=$(curl -s -m4 "http://127.0.0.1:$p/v1/models" 2>/dev/null | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  [ -n "$M" ] && { PORT="$p"; break; }
done
echo "engine port=$PORT model=$M"
NC=$(curl -s -m4 "http://127.0.0.1:$PORT/props" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("default_generation_settings",{}).get("n_ctx"))' 2>/dev/null)
echo "runtime n_ctx = $NC"
[ "$NC" = "$NEWCTX" ] && echo "VERIFY_OK n_ctx=$NEWCTX" || { echo "VERIFY_FAIL n_ctx=$NC (expect $NEWCTX)"; exit 4; }
echo "--DONE--"