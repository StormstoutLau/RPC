#!/bin/bash
# 查 9/1 deepseek-v4-flash 冒烟的实际启动命令（RPC 层分布方式）
echo "== 9/1 冒烟脚本 =="
ls -la d:/RPC/b6_smoke_deepseek.sh 2>/dev/null
cat d:/RPC/b6_smoke_deepseek.sh 2>/dev/null | head -30
echo
echo "== 台账/日志里 9/1 启动方式 =="
grep -riE "deepseek.*rpc|v4-flash.*rpc|--rpc.*deepseek|ot.*deepseek" d:/RPC --include="*.md" --include="*.sh" --include="*.py" 2>/dev/null | grep -v node_modules | head -10