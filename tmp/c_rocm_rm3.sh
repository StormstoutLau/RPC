#!/bin/bash
# C 站: 精确移除 ROCm 7.2.1 全套 (对齐 B 站: 无系统 ROCm/无 amdgpu-dkms-firmware/无 ROCm libdrm)
set +e
echo "=== 0. 备份已存在? ==="
ls -la /tmp/c_dpkg_rocm_before_20260908.txt 2>/dev/null | awk '{print $5, $9}'

echo "=== 1. 构造移除清单 (rocm/hip/miopen/hiptensor/racc/rccl + amdgpu-dkms-firmware + ROCm libdrm) ==="
# 明确保留: amdgpu-install meta(便于管理), 系统 libdrm-amdgpu1, linux-firmware-*
sudo -n dpkg --get-selections | awk '{print $1}' | grep -iE '^(rocm|hip|miopen|hiptensor|racc|rccl|hipcc|hipify)' > /tmp/rocm_purge_list.txt
echo "rocm/hip 系: $(wc -l < /tmp/rocm_purge_list.txt) 包"
cat /tmp/rocm_purge_list.txt | tr '\n' ' '; echo
echo "amdgpu-dkms-firmware (仅固件 blob, B 站无): 加入清单"
echo "amdgpu-dkms-firmware" >> /tmp/rocm_purge_list.txt
echo "ROCm 定制 libdrm (libdrm-amdgpu-amdgpu1 等, B 站无): 加入清单"
sudo -n dpkg --get-selections | awk '{print $1}' | grep -E 'amdgpu-amdgpu|amdgpu-common|amdgpu-dev|amdgpu-radeon' >> /tmp/rocm_purge_list.txt
echo "=== 移除前 amdgpu 驱动归属确认 (内核内置 amdgpu.ko 不受影响) ==="
modinfo amdgpu 2>/dev/null | grep -E '^filename' | head -1
echo "(filename 指向 /lib/modules/6.17.0-23-generic/kernel/... = 内核内置, 非 dkms, 不受包删除影响)"

echo "=== 2. 执行 apt purge ==="
PKGS=$(sort -u /tmp/rocm_purge_list.txt | tr '\n' ' ')
echo "待移除: $PKGS"
timeout 420 sudo -n apt-get remove --purge -y $PKGS 2>&1 | tail -25
echo "purge_exit=$?"

echo "=== 3. autoremove 清理孤儿依赖 ==="
timeout 180 sudo -n apt-get autoremove --purge -y 2>&1 | tail -6