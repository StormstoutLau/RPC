#!/usr/bin/env bash
# B 站预置预检：venv 状态 / g++ cmake 可用性（Cpp_Hub 试点 O-13 拆分余项）
set -u
echo "=== whoami/host ==="; whoami; hostname
echo "=== py3 ==="; python3 --version 2>&1; which python3
echo "=== existing agent venv candidates ==="
for p in ~/agent-workspaces/Cpp_Hub/.venv ~/agent-workspaces/paper/.venv; do
  echo "[$p]"; if [ -d "$p" ]; then ls "$p/bin" 2>/dev/null | head -20; else echo "  (absent)"; fi
done
echo "=== g++ ==="; g++ --version 2>&1 | head -1; which g++
echo "=== cmake ==="; cmake --version 2>&1 | head -1; which cmake
echo "=== make ==="; make --version 2>&1 | head -1
echo "=== pip pytest available (system) ==="; python3 -m pytest --version 2>&1 | head -1
echo "=== disk ==="; df -h ~ | tail -1
echo "DONE"