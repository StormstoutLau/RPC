#!/bin/bash
# a4_diag_bios.sh — 确认 A 站 BIOS carve-out 情况 (free 总内存 + VRAM carve-out 大小)
set -uo pipefail
echo "=== cmdline ==="
cat /proc/cmdline
echo "=== free -g (系统内存视角) ==="
free -g | head -2
echo "=== VRAM/GTT sysfs ==="
for d in /sys/class/drm/card*/device; do
  for f in mem_info_vram_total mem_info_vram_used mem_info_gtt_total mem_info_gtt_used; do
    [ -f "$d/$f" ] && printf "  %s %s = %s\n" "$(basename "$d")" "$f" "$(cat "$d/$f")"
  done
done
echo "=== grub ==="
grep -rn 'gttsize\|pages_limit\|vramlimit' /etc/default/grub /etc/default/grub.d/ 2>/dev/null || echo "no grub match"
echo "DIAG_BIOS_DONE"
