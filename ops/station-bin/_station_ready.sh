#!/bin/bash
# _station_ready.sh — D6 站环境就绪步骤 (O-19; C2 简化 2026-09-16)
# 在"运行本脚本的那台站"上执行, 使调用方确知该站引擎面就绪。
#
# 2026-09-16 (C2) 变更 —— 为什么不再注入:
#   · 引擎面 = unsloth studio 的**固定 8080** (实测提供 OpenAI /v1 + Anthropic /v1/messages +
#     Responses 三协议, 带 key 即可用; 内层 llama-server 端口随机且**不可指定** ——
#     `unsloth studio run` 把 --host/--port 列为 managed flag 拒收)。
#   · 旧实现在此**就地改写** opencode.jsonc 的 local.baseURL ⇒ 任务后留下死端口、三站 config
#     漂移 (门禁 stations 断言转红)、且只治 opencode 一支 (claude 走 settings.json 无人纠正)。
#   · 现改为: 端口固定 8080 (opencode/claude 的 baseURL 本就是它), **唯一需要保持新鲜的是
#     studio 每次加载重铸的 key** —— 由 infer-load 落盘到 ~/.config/rpc/unsloth.key
#     (opencode 的 {file:} 与 claude 的 apiKeyHelper 都读它)。故本脚本**不再写任何配置**。
#   · 端口发现整段删除: 裸 llama-server 已不是引擎面, 其 /slots 在 C2 形态下也不反映忙态
#     (slot-gate 已改走 /api/inference/active-generations)。
# 用法: bash _station_ready.sh [期望alias子串]
# 成功: STATION_READY port=8080 model=.. (+ENGINE_CTX/CHAT_OK) exit 0
#   引擎未加载或无响应: ERR_NO_ENGINE exit 10;  chat 往返失败: ERR_CHAT exit 12
set -uo pipefail
ALIAS="${1:-}"
PORT=8080
KEYF="$HOME/.config/rpc/unsloth.key"
K=""
[ -f "$KEYF" ] && K=$(tr -d '[:space:]' < "$KEYF" 2>/dev/null)

# ---- [1] 就绪: /v1/models ----
if [ -n "$K" ]; then
  MODELS=$(curl -s -m5 -H "Authorization: Bearer $K" "http://127.0.0.1:$PORT/v1/models" 2>/dev/null)
else
  MODELS=$(curl -s -m5 "http://127.0.0.1:$PORT/v1/models" 2>/dev/null)
fi
MODEL_ID=$(printf '%s' "$MODELS" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
if [ -z "$MODEL_ID" ]; then
  echo "ERR_NO_ENGINE: :$PORT /v1/models 无响应 (模型未加载? 或 key 未落盘 —— 见 infer-load)"
  exit 10
fi
echo "STATION_READY port=$PORT model=$MODEL_ID"
if [ -n "$ALIAS" ]; then
  if echo "$MODEL_ID" | grep -qi "$ALIAS"; then echo "MODEL_MATCH alias=$ALIAS ok"; else echo "WARN_MODEL_MISMATCH: 期望 $ALIAS, 实际 $MODEL_ID (利用现状继续)"; fi
fi

# ---- [2] 引擎 ctx (radical fix B: engine ctx = source of truth) ----
if [ -n "$K" ]; then
  V=$(curl -s -m5 -H "Authorization: Bearer $K" "http://127.0.0.1:$PORT/props" 2>/dev/null | grep -oE '"n_ctx":[[:space:]]*[0-9]+' | grep -oE '[0-9]+$' | head -1)
else
  V=$(curl -s -m5 "http://127.0.0.1:$PORT/props" 2>/dev/null | grep -oE '"n_ctx":[[:space:]]*[0-9]+' | grep -oE '[0-9]+$' | head -1)
fi
if [ -n "$V" ]; then
  echo "ENGINE_CTX=$V"
else
  echo "WARN_ENGINE_CTX_NA"
fi

# ---- [3] chat 往返 ----
# 判据 = 响应含 "choices" (请求被引擎受理并完成), **不看 content 是否非空**:
# reasoning 模型在 max_tokens 小时会把配额全花在 thinking 上 -> content 缺省/为空
# (2026-09-16 实测 gpt-oss-20b: max_tokens=8 时无 content 字段)。原实现以 content 判 => 假失败。
D='{"model":"x","messages":[{"role":"user","content":"say OK"}],"max_tokens":64}'
# ⚠ 必须显式 -H "Content-Type: application/json": 缺它 curl 默认按 form-urlencoded 发,
#   引擎侧 Pydantic 会报 "body: Input should be a valid dictionary" (2026-09-16 实测踩到)。
#   旧实现也缺此头 —— 其 CHAT_OK 实为**假阳性** (匹配到的 "content":"" 来自非正常响应)。
if [ -n "$K" ]; then
  RESP=$(curl -s -m60 -H "Content-Type: application/json" -H "Authorization: Bearer $K" "http://127.0.0.1:$PORT/v1/chat/completions" --data-raw "$D" 2>/dev/null)
else
  RESP=$(curl -s -m60 -H "Content-Type: application/json" "http://127.0.0.1:$PORT/v1/chat/completions" --data-raw "$D" 2>/dev/null)
fi
if printf '%s' "$RESP" | grep -q '"choices"'; then
  echo "CHAT_OK choices=1"
else
  echo "ERR_CHAT: 引擎 chat 无响应 (port=$PORT) resp=$(printf '%s' "$RESP" | head -c 120)"
  exit 12
fi
echo "READY_OK port=$PORT (C2: 端口固定 8080, 本脚本不改写任何配置)"
echo "--DONE--"
