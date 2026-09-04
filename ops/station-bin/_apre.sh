#!/bin/bash
# _apre.sh — A站(NEX) 卡死复现前置备份 + 部署三步
set -u
M=NEX
ts=$(date +%Y%m%d%H%M%S)
echo "== [1/3] 前置备份 =="
LOG="$HOME/.unsloth/run-gpt-oss-120b.log"
if [ -f "$LOG" ]; then
  cp "$LOG" "$LOG.pre-repro-${ts}"
  ls -l "$LOG" "$LOG.pre-repro-${ts}"
  echo "  原log行数: $(wc -l < "$LOG") 备份行数: $(wc -l < "$LOG.pre-repro-${ts}")"
else
  echo "  WARN: $LOG 不存在, 跳过日志备份"
fi
grep -oE 'sk-unsloth-[a-f0-9]+' "$LOG" 2>/dev/null | tail -1 > /tmp/pre-repro-key.txt
echo "  pre-repro-key.txt = $(cat /tmp/pre-repro-key.txt)"
echo "== [2/3] 部署复现脚本到 /tmp =="
cp /tmp/repro-fire.sh  /tmp/repro-fire-A.sh 2>/dev/null || echo "  WARN 无 repro-fire.sh"
cp /tmp/repro-check.sh /tmp/repro-check-A.sh 2>/dev/null || echo "  WARN 无 repro-check.sh"
ls -l /tmp/repro-fire-A.sh /tmp/repro-check-A.sh 2>/dev/null
echo "== [3/3] 确认 8080 + 当前模型 =="
ss -tln 2>/dev/null | grep ':8080'
echo "backup_ts=${ts}"
echo OK