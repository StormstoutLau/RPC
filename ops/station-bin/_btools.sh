#!/bin/bash
KEY=sk-unsloth-f5ec3cebea66f627889ae59edd8df5e3
echo "== 模拟 opencode: /v1/responses 带 tools + max_output_tokens=16384 =="
timeout 60 curl -s http://127.0.0.1:8080/v1/responses -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","input":"hi","max_output_tokens":16384,"tools":[{"type":"function","name":"shell","description":"run shell","parameters":{"type":"object","properties":{}}}]}' -o /tmp/resp.json -w "http=%{http_code}\n"
head -c 400 /tmp/resp.json
echo
echo "== 模拟 opencode: /v1/chat/completions 带 tool_choice + tools =="
timeout 60 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"hi"}],"max_tokens":16384,"tools":[{"type":"function","function":{"name":"shell","parameters":{"type":"object","properties":{}}}}]}' -o /tmp/cc.json -w "http=%{http_code}\n"
head -c 400 /tmp/cc.json