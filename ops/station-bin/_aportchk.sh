#!/bin/bash
echo "== 8087 /v1/models =="
timeout 60 curl -s http://127.0.0.1:8087/v1/models -H "Authorization: Bearer sk-unsloth-581f55854cb263e3ebbc3ba7914b9191" | head -c 400
echo
echo "== 8087 chat/completions 2+2 =="
timeout 90 curl -s http://127.0.0.1:8087/v1/chat/completions -H "Authorization: Bearer sk-unsloth-581f55854cb263e3ebbc3ba7914b9191" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? one number."}],"max_tokens":40,"temperature":0}' | head -c 400
echo
echo "== 实际底层端口 (kvq log) =="
grep -oe 'port [0-9]*' /home/scott-lau/.unsloth/run-gpt-kvq.log | sort -u | head