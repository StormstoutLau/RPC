#!/bin/bash
# _probe_ctx3.sh — 决定性返证：查 llama-server 真实运行时 n_ctx（/props）+ 模型加载参数
# /v1/models 只通告 n_ctx_train（训练上下文，如 131072），运行时 slot 上下文须查 /props。
# 若 /props 的 n_ctx=65536 => 根因是服务端加载 --ctx-size=65536，与 opencode 配置无关。
set -uo pipefail
ALIAS="${1:-}"
echo "== host: $(hostname)"
for p in $(ss -tlnp 2>/dev/null | grep 'llama-server' | grep -oE '127\.0\.0\.1:[0-9]+' | cut -d: -f2 | sort -un); do
  M=$(curl -s -m4 "http://127.0.0.1:$p/v1/models" 2>/dev/null | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  [ -n "$M" ] || continue
  echo "== engine port=$p model=$M"
  echo "--- /props (运行时 n_ctx 真相) ---"
  curl -s -m4 "http://127.0.0.1:$p/props" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("props parse fail:",e); sys.exit(0)
gs=d.get("default_generation_settings",{})
print("  runtime n_ctx =", gs.get("n_ctx"))
print("  n_ctx_train  =", d.get("model_path") and "see model" or "", gs.get("n_ctx_train"))
print("  model_path   =", d.get("model_path"))
'
  echo "--- /v1/models 通告字段 (含 meta) ---"
  curl -s -m4 "http://127.0.0.1:$p/v1/models" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("models parse fail:",e); sys.exit(0)
for m in d.get("data",[]):
    meta=m.get("meta",{}) or {}
    print("  id:", m.get("id"))
    for k in ("n_ctx_train","context_length","max_model_len","max_input_tokens","top_k","top_p"):
        if k in meta: print("   meta.%s = %s" % (k, meta[k]))
'
  echo "--- /v1/models 顶层额外字段 ---"
  curl -s -m4 "http://127.0.0.1:$p/v1/models" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
print("  object keys:", list(d.keys()))
'
done
echo "--DONE--"