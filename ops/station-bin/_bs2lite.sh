#!/bin/bash
# bs2-liteprobe.sh — 探测本机 LiteLLM 网关 (4000) 模型面 + 是否可达
set -u
echo "== :4000 listen? =="
ss -tln 2>/dev/null | grep ':4000' || echo "no 4000 (LiteLLM 未在本机)"
echo "== :8080 (unsloth) =="
ss -tln 2>/dev/null | grep ':8080' || echo "no 8080"
echo "== LiteLLM /v1/models (localhost) =="
curl -s --max-time 5 http://127.0.0.1:4000/v1/models 2>&1 | head -c 500 || echo "lite llm unreachable"
echo
echo "== free 档: opencode/nemotron 是远端还是 4000? 看 provider 声明 =="
echo "--config 查 nemotron-3.5-lightning-free provider --"
grep -iE 'nemotron|lightning-free|litellm|4000' "$HOME/.config/opencode/opencode.jsonc" 2>/dev/null | head
echo "== opencode auth providers 配置 (可能远端) =="
opencode auth list 2>/dev/null | head -20 || echo "no auth list"
echo OK