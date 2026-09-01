#!/bin/bash
# 关键实验: claudecode (B 站) 接本地 nemotron via litellm (OpenAI 兼容模式)
set -u
exec 2>&1
export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"

echo "=== 1. 内存门 + 加载 nemotron ==="
load-mem-gate 80 || exit 1
infer-load nvidia-nemotron-3-super 2>&1 | tail -2

echo "=== 2. claude headless 测试 (OpenAI 兼容 env 指向 litellm) ==="
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')
cd /tmp && rm -rf cc_test && mkdir cc_test && cd cc_test

# claude code 的 OpenAI 兼容接入: ANTHROPIC_BASE_URL 指向网关 + ANTHROPIC_AUTH_TOKEN
# litellm 支持 /v1/messages (anthropic 格式) 直通 — 测试之
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export ANTHROPIC_AUTH_TOKEN="$KEY"
timeout 120 claude -p "Reply with exactly: PONG" --model nemotron 2>&1 | tail -8
echo "exit=$?"

echo "=== 3. 卸载回干净态 ==="
infer-unload 2>&1 | tail -2
echo DONE_CC_TEST
