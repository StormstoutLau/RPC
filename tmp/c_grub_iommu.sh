#!/bin/bash
# C 站: GRUB 追加 amd_iommu=off + ttm.pages_limit=32000000 (软件层最后一招, 可逆)
set +e
echo "=== 0. 备份 ==="
sudo -n cp /etc/default/grub /etc/default/grub.bak-before-iommu-20260908 && echo '备份完成' || echo '备份失败'
echo "=== 1. 修改前 ==="
grep '^GRUB_CMDLINE_LINUX_DEFAULT' /etc/default/grub

echo "=== 2. 修改 (sed) ==="
sudo -n sed -i 's|GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amdgpu.gttsize=120000 ttm.pages_limit=30720000"|GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amdgpu.gttsize=120000 ttm.pages_limit=32000000 amd_iommu=off"|' /etc/default/grub
echo "=== 3. 修改后 ==="
grep '^GRUB_CMDLINE_LINUX_DEFAULT' /etc/default/grub

echo "=== 4. update-grub ==="
sudo -n update-grub 2>&1 | tail -5
echo "exit=$?"

echo "=== 5. 校验收尾 ==="
grep '^GRUB_CMDLINE_LINUX' /etc/default/grub