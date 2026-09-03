#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-kvq.log
echo "== 日志尾部 =="
tail -30 "$LOG"
echo "== API Key / Running / Model loaded =="
grep -iE "API Key|Running at|Model loaded|error|fail|listening" "$LOG" | tail -10