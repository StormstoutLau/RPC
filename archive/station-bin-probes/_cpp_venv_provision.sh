#!/usr/bin/env bash
# B 站 Cpp_Hub 工作区 venv 预置（O-13 拆分余项：仅 venv，编译链已就绪）
set -euo pipefail
W=~/agent-workspaces/Cpp_Hub
mkdir -p "$W"
echo "=== create venv ==="
python3 -m venv "$W/.venv"
echo "=== venv python ==="
"$W/.venv/bin/python" --version
echo "=== upgrade pip + pytest ==="
"$W/.venv/bin/python" -m pip install --quiet --upgrade pip pytest
echo "=== verify pytest ==="
"$W/.venv/bin/python" -m pytest --version
echo "=== drop-in test: run Cpp_Hub pytest scaffold (placeholder dir, tests copied by sync soon) ==="
echo "DONE"