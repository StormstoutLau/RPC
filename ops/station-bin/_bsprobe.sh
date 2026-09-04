#!/bin/bash
# bsprobe.sh — BS-1 前置探测: opencode 安装 + db 位置 (只读)
set -u
echo "== opencode which =="
command -v opencode || echo "no opencode PATH"
which opencode 2>/dev/null
echo "== opencode version =="
opencode --version 2>/dev/null || echo "no version"
echo "== 默认 XDG_DATA_HOME =="
echo "XDG_DATA_HOME=${XDG_DATA_HOME:-<unset>}"
ls -ld "${XDG_DATA_HOME:-$HOME/.local/share}" 2>/dev/null
echo "== opencode.db 位置探测 =="
DB="${XDG_DATA_HOME:-$HOME/.local/share}/opencode"
echo "opencode data dir: $DB"
find "$DB" -maxdepth 2 -name '*.db' 2>/dev/null || echo "no db found"
ls -la "$DB" 2>/dev/null || echo "no opencode data dir"
echo "== 是否有 task/agent 工具面 (opencode config) =="
cat "$HOME/.config/opencode/opencode.jsonc" 2>/dev/null | head -50 || echo "no opencode.jsonc"
echo OK