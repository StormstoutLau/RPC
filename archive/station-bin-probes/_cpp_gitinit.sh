#!/usr/bin/env bash
# B 站 Cpp_Hub 工作区 git init（单向流不变式 6：试点项目须为 git 仓库）
set -u
W=~/agent-workspaces/Cpp_Hub
cd "$W" || { echo "NO_WORKSPACE"; exit 1; }
if [ -d .git ]; then echo "already-git"; else
  git init -q -b main
  git config user.email "peng.liu.john@gmail.com"
  git config user.name "scott-lau"
  echo "git-initialized"
fi
# 忽略流出产物/构建
if ! grep -q '^out/' .gitignore 2>/dev/null; then
  { echo ""; echo "out/"; echo "build/"; echo ".golden/"; } >> .gitignore
fi
git add -A 2>/dev/null
git status --short 2>/dev/null | head -20
echo "DONE"