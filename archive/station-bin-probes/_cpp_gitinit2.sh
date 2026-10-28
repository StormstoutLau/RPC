#!/usr/bin/env bash
set -u
cd ~/agent-workspaces/Cpp_Hub || { echo NO_WS; exit 1; }
git rm -r --cached .venv -q 2>/dev/null
if ! grep -q '^.venv/' .gitignore 2>/dev/null; then echo ".venv/" >> .gitignore; fi
echo "*.pyc" >> .gitignore
git add .gitignore 2>/dev/null
git add -A 2>/dev/null
echo "=== status (.venv 不应出现) ==="
git status --short 2>/dev/null | grep -v '^ $' | head -20
git commit -q -m "chore: Cpp_Hub 骨架（排除 .venv/.golden/build/out）" 2>&1 | head -5
echo "DONE"