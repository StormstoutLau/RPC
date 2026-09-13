#!/bin/bash
# C 站: 移除 radeon 源 + 终态验证
set +e
echo "=== 0. 备份 radeon 源 ==="
sudo -n mkdir -p /etc/apt/sources.list.d/backup-radeon-20260908
sudo -n cp -a /etc/apt/sources.list.d/amdgpu.list /etc/apt/sources.list.d/rocm.list /etc/apt/sources.list.d/amdgpu-proprietary.list /etc/apt/sources.list.d/backup-radeon-20260908/ 2>/dev/null
sudo -n ls /etc/apt/sources.list.d/backup-radeon-20260908/ 2>/dev/null
echo "=== 1. 移除 radeon 源文件 ==="
sudo -n rm -f /etc/apt/sources.list.d/amdgpu.list /etc/apt/sources.list.d/rocm.list /etc/apt/sources.list.d/amdgpu-proprietary.list /etc/apt/sources.list.d/amdgpu.list.save 2>/dev/null
echo "剩余 sources:"
ls /etc/apt/sources.list.d/ 2>/dev/null
echo "=== 2. apt update 干净性 ==="
timeout 120 sudo -n apt-get update 2>&1 | grep -iE '命中|获取|错误|W:' | tail -8
echo "=== 3. 关键服务验证 ==="
echo "-- qwen 18080 --"
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/users:.*/:(qwen on 18080)/' || echo '(未监听!)'
echo "-- unsloth 引擎 --"
~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -4
echo "-- ~/llama.cpp 引擎 --"
/home/scott-lau/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -4
echo "=== 4. amdgpu 驱动仍加载 ==="
lsmod 2>/dev/null | grep amdgpu | awk '{print $1, $2}' | head -2
echo "=== 5. 内存 ==="
free -g | head -2