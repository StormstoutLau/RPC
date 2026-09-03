#!/bin/bash
pkill -9 -f "opencode run" 2>/dev/null; pkill -9 -f "claude -p" 2>/dev/null; pkill -9 -x claude 2>/dev/null
echo "== unsloth 日志：最近请求/错误 =="
grep -iE "request_completed|status_code|401|403|unauth|/v1/(messages|chat)|error|tool" /home/scott-lau/.unsloth/run-gpt-8080-rst.log 2>/dev/null | tail -20 || echo "(无请求日志)"
echo "== 底层 llama-server 日志尾 =="
LL=$(grep -oE "/home/[^ ]*/logs/llama-server/[^ ]*\.log" /home/scott-lau/.unsloth/run-gpt-8080-rst.log | tail -1); echo "log=$LL"; tail -8 "$LL" 2>/dev/null