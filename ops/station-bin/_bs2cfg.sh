#!/bin/bash
# bs2-litecfg.sh — 查看 LiteLLM config.yaml (只读)
set -u
F="$HOME/litellm/config.yaml"
if [ -f "$F" ]; then
  echo "== $F =="
  cat "$F"
else
  echo "no $F"
fi
echo "== 其他 config 候选 =="
find "$HOME" -maxdepth 3 -name 'config*.yaml' -path '*litellm*' 2>/dev/null
echo OK