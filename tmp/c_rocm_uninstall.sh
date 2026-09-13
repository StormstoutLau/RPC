#!/bin/bash
# C 站: 移除 ROCm 7.2.1 (与 B 站同构: 无系统 ROCm)
set +e
echo "=== 0. 备份 dpkg 包状态 ==="
sudo -n dpkg --get-selections | grep -iE 'rocm|hip|amdgpu|miopen|hiptensor' > /tmp/c_dpkg_rocm_before_20260908.txt
wc -l /tmp/c_dpkg_rocm_before_20260908.txt
echo "(备份已存 /tmp/c_dpkg_rocm_before_20260908.txt)"

echo "=== 1. 官方 amdgpu-install --uninstall (dry-list 前先看帮助) ==="
amdgpu-install --help 2>&1 | grep -iE 'uninstall|usecase' | head -5

echo "=== 2. 执行卸载 (--uninstall --yes) ==="
timeout 300 sudo -n amdgpu-install --uninstall --yes 2>&1 | tail -15
echo "uninstall_exit=$?"