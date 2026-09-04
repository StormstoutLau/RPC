#!/bin/bash
# repro-health.sh — 复现后健康确认 + 备份文件留档核对
echo "== 8080 listening =="
ss -tln 2>/dev/null | grep ":8080"
echo "== 残留 repro 进程 =="
ps -eo pid,cmd | grep "[r]epro" || echo none
echo "== models 健康 =="
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$HOME/.unsloth/run-gpt-oss-120b.log" | tail -1)
curl -s -o /dev/null -w "models HTTP_%{http_code}\n" --max-time 3 -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/v1/models
echo "== 备份留档 =="
ls -l "$HOME/.unsloth/"*pre-repro* 2>/dev/null
echo OK