#!/bin/bash
# B 站本机 nohup 跑 Nemotron domain_matrix（进程独立于会话）
cd /tmp
mkdir -p /tmp/res_nem120b
nohup python3 /tmp/run_questions.py \
  "http://127.0.0.1:8095" \
  /tmp/questions.json \
  /tmp/res_nem120b \
  --model-name Nemotron-3-Super-120B \
  --max-tokens 12000 \
  > /tmp/res_nem120b/runner.log 2>&1 &
sleep 1
pgrep -af run_questions | grep -v grep || echo "runner 启动失败"
echo "STARTED"