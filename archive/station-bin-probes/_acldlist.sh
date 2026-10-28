#!/bin/bash
echo "== claude /model 列表 (含 custom) 尝试 =="
printf '/model\n' | timeout 20 claude --model gpt-oss-120b-MXFP4 -p "list" 2>&1 | head -30
echo "----"
echo "== claude --list-models 或内置 =="
timeout 20 claude --model 2>&1 | tail -20