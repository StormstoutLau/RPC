#!/bin/bash
# _apost.sh — A站(NEX) 复现后健康确认 + 残留进程 + 备份核对
LOG="$HOME/.unsloth/run-gpt-oss-120b.log"
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$LOG" | tail -1)
echo "== 8080 listen =="
ss -tln 2>/dev/null | grep ':8080'
echo "== 残留 repro 进程 =="
ps -eo pid,etime,cmd | grep -E '[r]epro-(launch|fire)' || echo "none"
echo "== 健康 (带key) =="
curl -s -o /dev/null -w "models HTTP_%{http_code}\n" --max-time 5 -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/v1/models
echo "== 简单生成冒烟 =="
curl -s --max-time 180 -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","prompt":"2+3=","max_tokens":6,"temperature":0}' \
  http://127.0.0.1:8080/v1/completions | python3 -c "import sys,json; d=json.load(sys.stdin); print('text=',d['choices'][0]['text'][:40])" 2>/dev/null || echo "(raw)"
echo "== 备份核对 =="
ls -l "$LOG.pre-repro-"* 2>/dev/null | tail -2
echo OK