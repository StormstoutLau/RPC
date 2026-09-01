#!/bin/bash
# A 站端口判定: config error 口 (usb8) 归属 vs TB NHI 归属
echo "=== config error 口的 PCI 归属 (全部 root hub) ==="
for rh in $(ls /sys/bus/usb/devices/ | grep -E '^usb[0-9]+$'); do
  pci=$(readlink -f /sys/bus/usb/devices/$rh | sed 's|.*/0000:|0000:|; s|/usb.*||')
  echo "$rh -> $pci"
done
echo
echo "=== TB NHI PCI 位置 ==="
for d in /sys/bus/thunderbolt/devices/domain*/; do
  echo "$(basename $d) -> $(readlink -f $d | grep -oE '0000:[0-9a-f:.]+/domain' | sed 's|/domain||')"
done
echo
echo "=== 全部 USB controller (PCI) ==="
lspci -nn | grep -i 'usb controller'
echo
echo "=== 00:08.x bridge 归属 ==="
lspci -nn | grep -E '00:08\.[13]'
