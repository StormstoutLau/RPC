#!/bin/bash
# C 站: 检查当前剩余 ROCm 包 + 重试正确提取
set +e
echo "=== 1. 当前剩余 rocm/hip 包 ==="
dpkg -l 2>/dev/null | grep -iE 'rocm|hip|miopen|hiptensor|amdgpu' | awk '{print $2}' | head -40
echo "=== 2. dpkg --get-selections 输出格式确认 ==="
dpkg --get-selections 2>/dev/null | grep -i '^rocm' | head -5
echo "=== 3. /opt/rocm 现状 ==="
ls -la /opt/ 2>/dev/null | grep -i rocm
echo "=== 4. rocminfo 是否还在 ==="
which rocminfo 2>/dev/null || echo '(rocminfo 已移除)'