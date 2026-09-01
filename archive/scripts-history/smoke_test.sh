#!/bin/bash
# API 冒烟: 1-token 推理探活 (A2 试验后全链路恢复验证)
curl -s http://192.168.1.15:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax","messages":[{"role":"user","content":"say ok"}],"max_tokens":5}' \
  | head -c 300
echo
