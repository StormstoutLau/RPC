#!/bin/bash
# bs2-litestatus.sh — 本机 LiteLLM 网关状态与日志 (只读诊断)
set -u
echo "== 4000 属主进程 =="
ss -tlnp 2>/dev/null | grep ':4000'
echo "== LiteLLM 进程 =="
ps -eo pid,etime,cmd | grep -iE '[l]itellm|[l]lm.?proxy' | head -5
echo "== 常见日志位置 =="
ls -la "$HOME/.litellm/"* 2>/dev/null | tail -10
ls -la /var/log/litellm* 2>/dev/null
find "$HOME" -maxdepth 3 -name '*litellm*.log' 2>/dev/null | head
echo "== 端口冲突: 谁真在 4000 =="
pid=$(ss -tlnp 2>/dev/null | grep ':4000' | grep -oP 'pid=\K[0-9]+' | head -1)
echo "pid=$pid"
[ -n "$pid" ] && ps -p "$pid" -o pid,etime,cmd 2>/dev/null
echo OK