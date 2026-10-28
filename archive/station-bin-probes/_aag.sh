#!/bin/bash
echo "== claude CLI 是否安装 =="
command -v claude && claude --version 2>&1 | head -1 || echo "claude 未安装"
echo "== opencode 是否安装 + 模型id =="
command -v opencode && opencode --version 2>&1 | head -1 || echo "opencode 未安装"
echo "== A opencode provider gpt-oss 相关 (cluster-local/litellm) =="
grep -A6 '"cluster-local"' ~/.config/opencode/opencode.jsonc 2>/dev/null | head -12
echo "== 当前未占用端口 8080? =="
ss -tlnp 2>/dev/null | grep ':8080' | head || echo "8080 空闲"