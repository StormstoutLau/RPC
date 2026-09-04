#!/bin/bash
# repro-probe.sh — 复现前只读探测: 槽位/端点/key/模型 (在站上执行)
LOG="$HOME/.unsloth/run-gpt-oss-120b.log"
echo "== 运行行 =="
grep -oE 'n_parallel[^,]*' "$LOG" | tail -3
grep -oE 'running at http://[0-9.:]+' "$LOG" | tail -2
grep -oE 'API Key: [a-z0-9-]*' "$LOG" | tail -1
echo "== backend/model =="
grep -oE 'Using device: [^ ]*' "$LOG" | tail -1
grep -oE 'model [^ ]*gguf' "$LOG" | tail -1
echo "== 健康(v1/models 带认证) =="
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$LOG" | tail -1)
P=$(grep -oE 'running at http://127.0.0.1:[0-9]+' "$LOG" | tail -1 | grep -oE '[0-9]+$')
echo "port=$P keylen=${#KEY}"
curl -sf --max-time 3 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$P/v1/models" | head -c 300
echo ""
echo "== slots(list 端点) =="
curl -sf --max-time 3 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$P/slots" | head -c 400
echo ""
echo OK