#!/bin/bash
KEY=sk-unsloth-60153365833b5b5fa37954a69ddd4c07
for M in "gpt-oss" "cluster-local/gpt-oss" "gpt-oss-120b-MXFP4"; do
  echo "== model=$M =="
  timeout 120 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$M\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply OK\"}],\"max_tokens\":24,\"temperature\":0}" 2>&1 | head -c 260
  echo
done