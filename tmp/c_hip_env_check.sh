#!/bin/bash
# C 站 HIP 引擎库链接与 ROCm 环境检查
set +e
echo '=== 1. ldd 引擎 HIP 依赖 ==='
ldd ~/.unsloth/llama.cpp/build/bin/llama-server 2>/dev/null | grep -iE 'hip|hc|amdx|rocm'
echo '=== 2. LD_LIBRARY_PATH ==='
echo "${LD_LIBRARY_PATH:-<empty>}"
echo '=== 3. ROCm/HIP 环境变量 ==='
env | grep -iE 'ROCM|HIP|HSA'
echo '=== 4. 引擎自带 libamdhip ==='
ls -la ~/.unsloth/llama.cpp/build/bin/ | grep -iE 'hip|hsa' | head -8
echo '=== 5. 系统 ROCm 的 lib ==='
ls -la /opt/rocm/lib/libamdhip64.so* /opt/rocm-7.2.1/lib/libamdhip64.so* 2>/dev/null | head -8
echo '=== 6. KFD 版本 ==='
cat /sys/class/kfd/kfd/features 2>/dev/null | head -3
cat /sys/class/kfd/kfd/version 2>/dev/null