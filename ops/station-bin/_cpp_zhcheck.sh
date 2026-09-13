#!/usr/bin/env bash
# O-06 中文路径验证：确认 Cpp_Hub 中文文件名在 B 站工作区正确落地（无乱码/改名）
set -u
W=~/agent-workspaces/Cpp_Hub
echo "=== ls src (期望显示中文名, 不可为 ???? 或八进制转义) ==="
ls -1 "$W/src" | cat -A
echo "=== git status of Chinese files ==="
cd "$W" 2>/dev/null && git status --short 2>/dev/null | head -20 || echo "(not a git repo yet)"
echo "=== find 中文文件名 count ==="
find "$W" -name "*因子*" 2>/dev/null | sort
echo "=== file content head (UTF-8 校验) ==="
for f in "$W"/src/因子计算_核心.cpp "$W"/src/因子计算_run.cpp; do
  if [ -f "$f" ]; then echo "[$f]"; head -3 "$f"; else echo "MISSING: $f"; fi
done
echo "DONE"