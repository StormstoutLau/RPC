#!/bin/bash
# repro-parallel.sh — 确认 unsloth 实例实际并行槽位配置 (只读)
LOG="$HOME/.unsloth/run-gpt-oss-120b.log"
echo "== 启动参数全文(前60行含 parallel/slots/np) =="
grep -inE 'parallel|slots|n_parallel|\-np |context\b' "$LOG" | head -15
echo "== /slots 端点 raw =="
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$LOG" | tail -1)
curl -s -w "\nHTTP_%{http_code}\n" --max-time 3 -H "Authorization: Bearer $KEY" "http://127.0.0.1:8080/slots"
echo "== /v1/internal slot 端点 =="
curl -s -w "\nHTTP_%{http_code}\n" --max-time 3 -H "Authorization: Bearer $KEY" "http://127.0.0.1:8080/v1/internal/slot"
echo "== tail 20 =="
tail -20 "$LOG"
echo OK