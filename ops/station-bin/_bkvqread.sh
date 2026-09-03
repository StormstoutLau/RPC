#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-bkvq.log
echo "== 日志尾部 =="
tail -25 "$LOG"
echo "== key/running/model/kv =="
grep -iE "API Key|running at|Model loaded|Context length|cache-type-k|cache-type-v|est. KV|error|fail" "$LOG" | tail -12