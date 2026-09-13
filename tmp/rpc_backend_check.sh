#!/bin/bash
# 核实: 当前 rpc-server 后端 + unsloth HIP 构建是否含 RPC worker
set +e
echo "=== 1. A 站当前 rpc-server 进程与加载库 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "
  ps -eo cmd | grep ggml-rpc-server | grep -v grep | head -2
  echo '-- 加载的 ggml 库 --'
  RPID=\$(pgrep -f ggml-rpc-server | head -1)
  [ -n \"\$RPID\" ] && grep -oE 'libggml-(vulkan|hip|rpc|base)[^ ]*' /proc/\$RPID/maps | sort -u | head -8
"
echo ""
echo "=== 2. A 站 unsloth HIP 构建是否含 ggml-rpc-server ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "
  ls ~/.unsloth/llama.cpp/build/bin/ | grep -E 'rpc|llama-server' | head -5
  echo '-- ./opt 构建的 rpc 组件 --'
  ls /opt/llama.cpp/ | grep -iE 'rpc' | head -5
"
echo ""
echo "=== 3. A 站 master /opt 构建后端 (vulkan? hip?) ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "
  ls /opt/llama.cpp/build/bin/ 2>/dev/null | grep -iE 'vulkan|hip|rpc' | head -5
  echo '-- llama-server list-devices (后端口) --'
  /opt/llama.cpp/llama-server --list-devices 2>&1 | head -3
"