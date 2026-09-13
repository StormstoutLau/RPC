#!/bin/bash
# C 站: 恢复 aqlprofile + 深挖故障上下文
set +e
echo "=== 0. 恢复 aqlprofile ==="
sudo -n mv /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64.so.1.0.70201.bak-hip-test /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64.so.1.0.70201 2>/dev/null && echo '已恢复' || echo '恢复失败'
ls -la /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64* 2>/dev/null | tail -2

echo "=== 1. 完整 amdgpu 事件 (最近 40 行) ==="
sudo -n dmesg -T 2>/dev/null | grep -iE 'amdgpu|kfd|drm' | tail -40
echo ""
echo "=== 2. GPU reset / hang 记录 ==="
sudo -n dmesg -T 2>/dev/null | grep -iE 'reset|hang|timeout|evict' | tail -10