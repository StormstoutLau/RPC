#!/bin/bash
echo "== 派生 llama-server 命令行 (看 reasoning) =="
grep -oE "llama-server -m [^ ]+ .*" /home/scott-lau/.unsloth/run-gpt-8080-rst.log | head -1
echo "== 是否出现 Reasoning 相关提示 =="
grep -iE "reasoning_effort|Reasoning model|reasoning.*off|--reasoning" /home/scott-lau/.unsloth/run-gpt-8080-rst.log | tail -4
echo "== 8080 health =="
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/health 2>&1