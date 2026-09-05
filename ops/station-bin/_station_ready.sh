#!/bin/bash
# _station_ready.sh — D6 站环境就绪步骤（最小落地，O-19）
# 在"运行本脚本的那台站"上执行，使 opencode 可连到该站真实的 llama-server 引擎端点。
#   1) 发现 llama-server 引擎端口（8080 是 unsloth studio 管理端，不承载推理 → 不可用）
#   2) 校验 /v1/models 返回模型 id + chat 往返（无鉴权）
#   3) 幂等改写 opencode.jsonc 的 `cluster-litellm` provider baseURL -> 引擎端口
# 用法: bash _station_ready.sh [期望alias子串]   # 如 gpt-oss
# 成功: 打印 STATION_READY port=.. model=.. + INJECT_OK; exit 0
#   若引擎未加载: ERR_NO_ENGINE exit 10
#   若注入失败:   ERR_INJECT exit 11
set -uo pipefail
ALIAS="${1:-}"
CFG="$HOME/.config/opencode/opencode.jsonc"

# ---- [1] 发现引擎端口（仅 llama-server，非 unsloth studio）----
PORT=""; MODEL_ID=""
for p in $(ss -tlnp 2>/dev/null | grep 'llama-server' | grep -oE '127\.0\.0\.1:[0-9]+' | cut -d: -f2 | sort -un); do
  M=$(curl -s -m4 "http://127.0.0.1:$p/v1/models" 2>/dev/null | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  if [ -n "$M" ]; then PORT="$p"; MODEL_ID="$M"; break; fi
done
if [ -z "$PORT" ]; then
  echo "ERR_NO_ENGINE: 无 llama-server 引擎端口 (模型未加载? 先 load-mem-gate + infer-load)"
  exit 10
fi

# ---- [2a] /v1/models 校验 ----
echo "STATION_READY port=$PORT model=$MODEL_ID"
if [ -n "$ALIAS" ]; then
  if echo "$MODEL_ID" | grep -qi "$ALIAS"; then echo "MODEL_MATCH alias=$ALIAS ok"; else echo "WARN_MODEL_MISMATCH: 期望 $ALIAS, 实际 $MODEL_ID (利用现状继续)"; fi
fi

# ---- [2b] chat 往返校验 ----
CHAT=$(curl -s -m20 "http://127.0.0.1:$PORT/v1/chat/completions" \
  --data-raw '{"model":"'$MODEL_ID'","messages":[{"role":"user","content":"say OK"}],"max_tokens":8}' 2>/dev/null \
  | grep -oE '"content":"[^"]*"' | head -1)
echo "CHAT_OK $CHAT"
[ -n "$CHAT" ] || { echo "ERR_CHAT: 引擎 chat 无响应 (port=$PORT)"; exit 12; }

# ---- [3] 幂等注入 cluster-litellm baseURL -> 引擎端口 ----
if [ ! -f "$CFG" ]; then echo "ERR_INJECT: 无 opencode config $CFG"; exit 11; fi
python3 - "$CFG" "$PORT" <<'PY'
import sys, re
cfg, port = sys.argv[1], sys.argv[2]
s = open(cfg, encoding='utf-8').read()
m = re.search(r'\n {4}"cluster-litellm"\s*:\s*\{', s) or re.search(r'"cluster-litellm"\s*:\s*\{', s)
if not m:
    print("ERR_INJECT: 无 cluster-litellm provider"); sys.exit(11)
start = m.end()
rest = s[start:]
nxt = re.search(r'\n {4}"[^"]+"\s*:\s*\{', rest)
close = re.search(r'\n {2}\}', rest)
end = len(rest)
if nxt and nxt.start() < end: end = nxt.start()
if close and close.start() < end: end = close.start()
block = rest[:end]
if '"baseURL"' not in block:
    print("ERR_INJECT: cluster-litellm 块内无 baseURL"); sys.exit(11)
newblock = re.sub(r'"baseURL"\s*:\s*"[^"]*"', '"baseURL": "http://127.0.0.1:%s/v1"' % port, block, count=1)
open(cfg, 'w', encoding='utf-8').write(s[:start] + newblock + rest[end:])
print("INJECT_OK port=%s" % port)
PY
rc=$?
[ $rc -eq 0 ] || exit 11

# ---- [4] 注入后复核：baseURL 已指向引擎端口 ----
grep -q "127.0.0.1:$PORT/v1" "$CFG" || { echo "ERR_INJECT_VERIFY: 复核失败"; exit 11; }
echo "INJECT_VERIFY_OK -> $PORT"
echo "--DONE--"