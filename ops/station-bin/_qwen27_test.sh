#!/bin/bash
# Inference test for Qwen3.8-27B-MTP on :18080 (2026-09-06)
BASE=http://127.0.0.1:18080
echo "=== /props spec info ==="
curl -s --max-time 3 "$BASE/props" | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k:d.get(k) for k in ("spec_type","spec_n_max","n_ctx","model_path","model_alias") if k in d})' 2>&1
echo
echo "=== completion test (n_predict=200) ==="
T0=$(date +%s.%N)
RESP=$(curl -s --max-time 120 "$BASE/completion" -H 'Content-Type: application/json' -d '{
  "prompt": "写一段关于量化金融中因子投资的中文技术说明，不超过200字：",
  "n_predict": 200, "temperature": 0.0, "cache_prompt": false
}')
T1=$(date +%s.%N)
DT=$(echo "$T1 $T0" | awk '{printf "%.2f", $1-$2}')
GT=$(echo "$RESP" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("timings",{}).get("predicted_per_second","NA"))' 2>/dev/null)
TOK=$(echo "$RESP" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("timings",{}).get("predicted_n","NA"), d.get("timings",{}).get("prompt_n","NA"))' 2>/dev/null)
echo "wall=${DT}s  predicted_per_second=${GT}  (predicted_n prompt_n)=${TOK}"
echo "--- sample text ---"
echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("content","")[:300])' 2>&1
echo
echo "=== chat test (MTP through template) ==="
curl -s --max-time 60 "$BASE/v1/chat/completions" -H 'Content-Type: application/json' -d '{
  "model": "qwen3.8-27b-mtp",
  "messages":[{"role":"user","content":"用一句话回答：什么是投机解码？"}],
  "max_tokens":60, "temperature":0.0
}' | python3 -c 'import sys,json; d=json.load(sys.stdin); c=d.get("choices",[{}])[0].get("message",{}).get("content",""); u=d.get("usage",{}); print("content:",c); print("usage:",u)' 2>&1