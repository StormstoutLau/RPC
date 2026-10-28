#!/bin/bash
# _ahealth.sh — A站(NEX) unsloth 健康确认 (带鉴权 key)
LOG="$HOME/.unsloth/run-gpt-oss-120b.log"
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$LOG" | tail -1)
echo "hostname=$(hostname) keylen=${#KEY}"
echo "=== models 健康 (带鉴权) ==="
curl -s -o /dev/null -w "models HTTP_%{http_code}\n" --max-time 5 -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/v1/models
echo "=== 简单生成冒烟 (2+2=) ==="
curl -s --max-time 180 -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","prompt":"2+2=","max_tokens":8,"temperature":0}' \
  http://127.0.0.1:8080/v1/completions | head -c 400
echo
echo "=== 8080 属主进程运行时长 ==="
ss -tlnp 2>/dev/null | grep ':8080'
echo "=== 内存 available ==="
free -g 2>/dev/null | grep -E '^[[:space:]]*(内存|Mem)'
echo OK