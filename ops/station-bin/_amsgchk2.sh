#!/bin/bash
echo "== Authorization: Bearer (Anthropic 通道) =="
timeout 60 curl -s http://127.0.0.1:8087/v1/messages \
  -H "Authorization: Bearer sk-unsloth-581f55854cb263e3ebbc3ba7914b9191" \
  -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","max_tokens":30,"messages":[{"role":"user","content":"2+2? one number."}]}' | head -c 400