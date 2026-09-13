#!/bin/bash
# C station: add AMD UMA kernel params to GRUB (align to B station) - BACKUP + apply + update
set -e
GRUB=/etc/default/grub
echo "=== before ==="
grep 'GRUB_CMDLINE_LINUX_DEFAULT' "$GRUB"
# backup (hard rule: destructive ops backup first)
sudo cp "$GRUB" "$GRUB.bak-c-20260907"
echo "backup: $GRUB.bak-c-20260907"
# inject params into GRUB_CMDLINE_LINUX_DEFAULT (idempotent)
sudo sed -i 's|^GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"|GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amdgpu.gttsize=120000 ttm.pages_limit=30720000"|' "$GRUB"
# safety: verify it took; if not (different default), patch any line containing GRUB_CMDLINE_LINUX_DEFAULT
if ! grep -q 'amdgpu.gttsize=120000' "$GRUB"; then
  echo "first sed missed, trying broader patch..."
  sudo sed -i 's|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amdgpu.gttsize=120000 ttm.pages_limit=30720000"|' "$GRUB"
fi
echo "=== after ==="
grep 'GRUB_CMDLINE_LINUX_DEFAULT' "$GRUB"
echo "=== update-grub ==="
sudo update-grub 2>&1 | tail -3