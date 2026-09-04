#!/bin/bash
# repro-check.sh — 读取复现结果与后端日志信号
echo "=== repro-fire.out (tail) ==="
tail -40 /tmp/repro-fire.out 2>/dev/null
echo "=== A/B rc ==="
echo "A_rc=$(cat /tmp/repro-A.rc 2>/dev/null || echo none)"
echo "B_rc=$(cat /tmp/repro-B.rc 2>/dev/null || echo none)"
echo "=== A/B out (head) ==="
echo "--- A.out ---"; head -c 200 /tmp/repro-A.out 2>/dev/null; echo
echo "--- B.out ---"; head -c 200 /tmp/repro-B.out 2>/dev/null; echo
echo "=== 后端日志 engine_stats (running/x) ==="
grep -oE '"event": "engine_stats", "gen_tok_s": [0-9.]*, "prompt_tok_s": [0-9.]*, "running": [0-9]*, "waiting": [0-9]*' ~/.unsloth/run-gpt-oss-120b.log | tail -10
echo "=== request_completed (最近) ==="
grep -oE '"event": "request_completed", "method": "[A-Z]+", "path": "[^"]*", "status_code": [0-9]*, "process_time_ms": [0-9.]*' ~/.unsloth/run-gpt-oss-120b.log | tail -6
echo OK