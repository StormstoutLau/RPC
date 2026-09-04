#!/bin/bash
# bs2-agents-ls.sh — 列出 opencode agents 定义 (只读)
set -u
D="$HOME/.config/opencode/agents"
echo "== agents 目录 =="
ls -la "$D" 2>&1
echo "== 每个 agent 文件内容 (前 30 行) =="
for f in "$D"/*; do
  [ -f "$f" ] || continue
  echo "----- $f -----"
  head -30 "$f"
done
echo OK