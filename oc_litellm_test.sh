#!/bin/bash
# 关键实验: B 站 opencode headless (无 PTY) 接 litellm 本地路由 nemotron
set -u
exec 2>&1

echo "=== 1. 内存门 + 加载 nemotron ==="
load-mem-gate 80 || exit 1
infer-load nvidia-nemotron-3-super 2>&1 | tail -2

echo "=== 2. 写 opencode 配置 (litellm 本地 provider) ==="
mkdir -p ~/.config/opencode
KEY=$(grep master_key /home/scott-lau/litellm/config.yaml | awk '{print $2}')
cat > ~/.config/opencode/opencode.jsonc <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "cluster-litellm": {
      "name": "Cluster LiteLLM",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:4000/v1",
        "apiKey": "$KEY"
      },
      "models": {
        "nemotron": { "name": "Nemotron 3 Super 120B (local)" },
        "gpt-oss": { "name": "GPT-OSS 120B (local)" }
      }
    }
  }
}
EOF
echo "配置已写入 (key 内嵌, 不回显)"

echo "=== 3. headless 测试 (无 -t, 无代理 — 本地 provider 是否免 PTY/keyring) ==="
cd /tmp && rm -rf oc_test && mkdir oc_test && cd oc_test
timeout 180 ~/.opencode/bin/opencode run -m cluster-litellm/nemotron 'Reply with exactly: PONG' 2>&1 | tail -5
echo "exit=$?"

echo "=== 4. 卸载回干净态 ==="
infer-unload 2>&1 | tail -2
echo DONE_OC_TEST
