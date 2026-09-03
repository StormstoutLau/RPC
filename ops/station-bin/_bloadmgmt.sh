#!/bin/bash
echo "=== 1) /usr/local/bin 加载管理脚本 ==="
ls -la /usr/local/bin/ | grep -iE "infer|llama|load|unload|mem|gtt"
echo
echo "=== 2) infer-load 内容 ==="
cat /usr/local/bin/infer-load 2>/dev/null | head -80
echo
echo "=== 3) infer-list ==="
cat /usr/local/bin/infer-list 2>/dev/null | head -40