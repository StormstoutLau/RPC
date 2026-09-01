#!/bin/bash
# B 站安装 claudecode cli (npm 全局, 走 nvm node v22.23.2)
set -u
exec 2>&1

export NVM_DIR="$HOME/.nvm"
export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"

echo "=== 1. 安装前确认 ==="
node --version; npm --version

echo "=== 2. npm 全局安装 @anthropic-ai/claude-code ==="
npm install -g @anthropic-ai/claude-code 2>&1 | tail -5

echo "=== 3. 验证 ==="
which claude
claude --version 2>&1 | head -1

echo "=== 4. PATH 持久化 (写入 .bashrc, nvm 已有则跳过) ==="
grep -q 'nvm/versions/node.*PATH' ~/.bashrc || echo 'export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"' >> ~/.bashrc
echo DONE_CC_INSTALL
