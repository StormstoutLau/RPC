#!/usr/bin/env bash
set -u
W=~/agent-workspaces/Cpp_Hub
echo "=== host ==="; hostname
echo "=== src dir ==="; ls -1 "$W/src" 2>&1 | cat -A
echo "=== 向量均值 present? ==="; grep -c "向量均值" "$W/src/因子计算_核心.cpp" 2>/dev/null || echo "0/no-file"
echo "=== 因子计算_run 内 --mean? ==="; grep -c "\-\-mean" "$W/src/因子计算_run.cpp" 2>/dev/null || echo "0/no-file"
echo "=== python3 ==="; python3 --version 2>&1
echo "=== .venv python? ==="; ls -l "$W/.venv/bin/python" 2>&1 | head -1
echo "=== git log ==="; git -C "$W" log --oneline -3 2>&1 | head -5
echo "=== git status ==="; git -C "$W" status --short 2>&1 | head -10
echo "=== out/ ==="; ls -la "$W/out" 2>&1 | head -10
echo "DONE"