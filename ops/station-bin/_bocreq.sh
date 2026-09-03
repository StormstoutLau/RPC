#!/bin/bash
echo "== 记录当前 server log 行数 =="
wc -l /home/scott-lau/.unsloth/studio/logs/server/server-20260904-020330-pid122013.log
echo "== 触发 opencode 一次 =="
echo 'Reply OK' | timeout 60 opencode run -m cluster-local/gpt-oss >/dev/null 2>&1
sleep 2
echo "== 新 append 的 server log (tracking /v1 请求) =="
tail -20 /home/scott-lau/.unsloth/studio/logs/server/server-20260904-020330-pid122013.log | grep -E "request_completed|path|status|openai|responses"