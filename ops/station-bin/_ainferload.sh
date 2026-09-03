#!/bin/bash
echo "== A 站现有 unsloth 实例 =="
ps -eo pid,cmd | grep "[u]nsloth studio run" | grep -oE "gpt-oss[^ ]*" | head
echo "== 跑 infer-load gpt-oss-120b (unsloth 后端) =="
infer-load 'gpt-oss-120b$' 2>&1 | head -25