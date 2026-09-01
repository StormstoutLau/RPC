#!/bin/bash
# fix_modules_extra.sh — A 站补装 linux-modules-extra-6.17.0-40 (修 6.17.0-40 显示/网络)
A="scott-lau@10.10.10.1"
echo "=== [1] 确认现状 (modules-extra 是否缺失) ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  echo "已装 6.17.0-40 相关包:"
  dpkg -l | grep "6.17.0-40" | awk "{print \$2}"
  echo "对比 7.0.0-30 modules-extra: $(dpkg -l linux-modules-extra-7.0.0-30-generic 2>/dev/null | grep ^ii | wc -l)"
'
echo
echo "=== [2] 补装 modules-extra ==="
timeout 240 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  sudo apt-get install -y linux-modules-extra-6.17.0-40-generic 2>&1 | tail -3
  echo "装后校验: $(dpkg -l linux-modules-extra-6.17.0-40-generic 2>/dev/null | grep ^ii | wc -l)"
  echo "amdgpu 模块文件存在: $(ls /lib/modules/6.17.0-40-generic/kernel/drivers/gpu/drm/amd/amdgpu/amdgpu.ko* 2>/dev/null | wc -l)"
  echo "thunderbolt 模块存在: $(ls /lib/modules/6.17.0-40-generic/kernel/drivers/thunderbolt/thunderbolt.ko* 2>/dev/null | wc -l)"
  echo "r8169 模块存在: $(ls /lib/modules/6.17.0-40-generic/kernel/drivers/net/ethernet/realtek/r8169.ko* 2>/dev/null | wc -l)"
'
echo
echo "=== [3] GRUB 钉扎仍有效确认 ==="
timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A 'grep ^GRUB_DEFAULT /etc/default/grub'