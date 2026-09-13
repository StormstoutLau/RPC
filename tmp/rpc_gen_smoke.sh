#!/bin/bash
# master 7B RPC 生成冒烟 (B 18099)
curl -s http://127.0.0.1:18099/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"Reply with exactly: PONG"}],"max_tokens":16}' \
  | head -c 500
echo