#!/bin/bash
# verify_modules.sh — 验证 6.17.0-40 模块解析 (dry-run, 不重启)
A="scott-lau@10.10.10.1"
timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "=== modules.dep 条目 ==="
  for m in amdgpu thunderbolt thunderbolt_net r8169; do
    echo -n "$m: "
    grep -c "kernel.*/$m.ko" /lib/modules/6.17.0-40-generic/modules.dep 2>/dev/null || echo 0
  done
  echo "=== modprobe dry-run (模拟 6.17.0-40 下 udev 加载) ==="
  for m in amdgpu thunderbolt thunderbolt_net r8169; do
    echo -n "$m: "
    sudo modprobe -S 6.17.0-40-generic --dry-run $m 2>&1 | head -1
    [ $? -eq 0 ] || echo "FAIL"
  done
  echo "=== firmware 依赖 (amdgpu 所需) ==="
  grep -oE "firmware/amdgpu/[^ ]*" /lib/modules/6.17.0-40-generic/modules.dep 2>/dev/null | head -2
  ls /lib/firmware/amdgpu/ 2>/dev/null | wc -l
'