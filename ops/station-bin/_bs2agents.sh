#!/bin/bash
# bs2-agents.sh — BS-2: 确认 opencode agent 工具面现状 (只读) + 是否支持扇出
set -u
echo "== opencode agent list =="
opencode agent list 2>&1 | head -20
echo "== 全局 agent 配置文件 =="
ls -la "$HOME/.config/opencode/agent/"* 2>/dev/null || echo "no agent dir"
find "$HOME/.config/opencode" -maxdepth 2 -iname '*agent*' 2>/dev/null
echo "== 是否已有 agent 定义 (json/md) =="
cat "$HOME/.config/opencode/agent/"*.md 2>/dev/null | head -20 || echo "no agent md"
echo OK