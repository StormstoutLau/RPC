#!/bin/bash
# C 站: 终态确认 + 落档数据
set +e
echo "=== 1. /opt 残留 ==="
ls -la /opt/ 2>/dev/null | grep -iE 'rocm|amd' || echo '(无 rocm/amd 残留)'
echo "=== 2. alternatives rocm 软链 ==="
ls -la /etc/alternatives/rocm 2>/dev/null || echo '(alternatives rocm 已清)'
echo "=== 3. ldconfig rocm 残留 ==="
ldconfig -p 2>/dev/null | grep -iE '/opt/rocm|libhsa|libamdhip' | head -5 || echo '(ldconfig 无 rocm 库)'
echo "=== 4. 环境变量残留 ==="
env | grep -iE 'ROCM|HIP|HSA' || echo '(无 ROCm/HIP/HSA 环境变量)'
echo "=== 5. 最终 ROCm 相关 dpkg 状态 ==="
dpkg -l 2>/dev/null | grep -iE 'rocm|hip|amdgpu' | awk '{print $1, $2, $3}' | head -10
echo "=== 6. 磁盘占用 (/opt 前后对照参考) ==="
du -sh /opt 2>/dev/null