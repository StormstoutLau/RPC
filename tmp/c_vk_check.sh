#!/bin/bash
# C 站: 确认 Vulkan 引擎与设备
set +e
echo "=== 1. Vulkan 引擎候选 ==="
ls -la /home/scott-lau/llama.cpp/build/bin/llama-server 2>/dev/null | awk '{print $5, $NF}'
/opt/llama.cpp/llama-server --version 2>&1 | head -1
ls -la /opt/llama.cpp/llama-server 2>/dev/null | awk '{print $5, $NF}'
echo "=== 2. Vulkan0 设备 ==="
/home/scott-lau/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -4
echo "=== 3. 当前状态 (应无进程/端口) ==="
pgrep -af llama-server || echo '(无 llama-server)'
ss -tlnp 2>/dev/null | grep -E '18080|18081|18082' || echo '(端口全释放)'
echo "=== 4. 内存 ==="
free -g | head -2
echo "=== 5. load-gate 60G ==="
bash /tmp/load-gate 60 2>&1 | tail -3