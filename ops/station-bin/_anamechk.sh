#!/bin/bash
echo "== curl 8087 用 gpt-oss-120b 名 =="
timeout 60 curl -s http://127.0.0.1:8087/v1/chat/completions -H "Authorization: Bearer sk-unsloth-581f55854cb263e3ebbc3ba7914b9191" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"2+2? one number."}],"max_tokens":20,"temperature":0}' | head -c 300
echo
echo "== claude code 版本 =="
claude --version 2>&1 | tail -1