#!/bin/bash
# 确认 M2.7 模型文件现状 (是否已删 + 越狱名标识)
set +e
echo "=== A 站 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "
  find /data/models /home/scott-lau/models -iname '*m2.7*' -o -iname '*minimax*m2*' 2>/dev/null | head -10
  echo '-- models 顶层 --'
  ls ~/models/ 2>/dev/null | head -10
  echo '-- data/models --'
  ls /data/models/ 2>/dev/null | head -10
"
echo ""
echo "=== B 站 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@scott-lau-GTR-Pro.local "
  find /data/models /home/scott-lau/models -iname '*m2.7*' 2>/dev/null | head -10
  echo '-- models 顶层 --'
  ls ~/models/ 2>/dev/null | head -10
"