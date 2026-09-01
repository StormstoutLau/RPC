#!/bin/bash
# a4_env_audit.sh — A4环境盘点: 内核/GPU/KFD/内存/TB链路 (两站通用)
# 用法: bash a4_env_audit.sh
echo "=== HOST ==="; hostname; uname -r
echo "=== GPU PCI ==="; lspci | grep -iE 'vga|display' || true
echo "=== KFD/DRM nodes ==="; ls -la /dev/kfd 2>/dev/null || echo "NO_KFD"; ls /dev/dri/ 2>/dev/null
echo "=== amdgpu driver version ==="
for f in /sys/class/drm/card*/device/driver_version; do
  [ -e "$f" ] && echo "$f = $(cat "$f")"
done 2>/dev/null || true
grep -ao 'amdgpu.*version=[0-9.]*' /sys/kernel/debug/dri/*/amdgpu_pm_info 2>/dev/null | head -1 || true
modinfo amdgpu 2>/dev/null | grep -E '^version|^filename' || echo "modinfo_unavailable"
echo "=== GTT/TTM ==="
for f in /sys/class/drm/card*/device/mem_info_vram_total /sys/class/drm/card*/device/mem_info_gtt_total; do
  [ -e "$f" ] && echo "$f = $(( $(cat "$f") / 1024 / 1024 / 1024 )) GiB"
done
echo "=== RAM ==="; free -g | head -2
echo "=== TB/USB4 net ==="
ip -br addr show 2>/dev/null | grep -E 'thunderbolt|usb|en' || true
echo "=== CPU EPP ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null || echo "no_epp"
echo "=== A4_AUDIT_DONE ==="
