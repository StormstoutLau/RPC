#!/bin/bash
# C 站: 按官方流程移除 ROCm 全套 (amdgpu-install 承装载有 --uninstall 真实动作)
set +e
echo "=== 0. 上次备份确认 ==="
wc -l /tmp/c_dpkg_rocm_before_20260908.txt

echo "=== 1. 卸载 amdgpu-install meta (触发 --uninstall 实际动作) ==="
timeout 420 sudo -n apt-get remove --purge -y amdgpu-install 2>&1 | tail -20
echo "meta_rm_exit=$?"