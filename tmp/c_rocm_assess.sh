#!/bin/bash
# C 站: ROCm 7.2.1 移除前评估 (列出相关包/依赖/apt 源)
set +e
echo "=== 1. /opt/rocm* 现状 ==="
ls -la /opt/ 2>/dev/null | grep -i rocm
echo "=== 2. rocm/hip 包清单 ==="
dpkg -l 2>/dev/null | grep -E 'rocm|hip|amdgpu' | awk '{print $2" "$3}' | head -40
echo "=== 3. radeon 源文件 ==="
ls -la /etc/apt/sources.list.d/ 2>/dev/null | grep -iE 'radeon|amdgpu|rocm'
cat /etc/apt/sources.list.d/amdgpu* 2>/dev/null | head -5
echo "=== 4. runtimes 是否依赖系统 rocm (引擎自带) === "
ldd ~/.unsloth/llama.cpp/build/bin/llama-server 2>/dev/null | grep -c 'build/bin' | xargs echo 'unsloth 自带库计数='
ldd /home/scott-lau/llama.cpp/build/bin/llama-server 2>/dev/null | grep -iE '/opt/rocm' | head -3
echo "(空=~/llama.cpp 不依赖系统 rocm)"
echo "=== 5. amdgpu-install 卸载工具 ==="
which amdgpu-uninstall amdgpu-install 2>/dev/null
echo "=== 6. 内存/服务现状 ==="
free -g | head -2
ss -tlnp 2>/dev/null | grep 18080 | head -1 | sed 's/.*users:/(pid info)/'