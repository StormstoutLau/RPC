#!/bin/bash
# Type-C 物理口判定: 找出线插在哪个口 + 该口是否 USB4
echo "=== typec 物理口列表 ==="
ls /sys/class/typec/ 2>/dev/null
echo
for p in /sys/class/typec/port*; do
  [ -d "$p" ] || continue
  name=$(basename $p)
  pd=$(cat $p/usb_power_delivery_revision 2>/dev/null)
  data=$(cat $p/data_role 2>/dev/null)
  # partner 存在 = 线缆已插入且对端被检测到
  partner="无"
  [ -d "$p/partner" ] && partner="有PARTNER(线已插)"
  echo "--- $name: PD=$pd data_role=$data partner=$partner"
  # 该口关联的 USB 设备 (判断挂在哪个 xHCI)
  for u in $p/usb* $p/*:*/usb*; do
    [ -e "$u" ] && echo "    usb 关联: $(basename $(dirname $u))/$(basename $u)"
  done
done
echo
echo "=== config error 口的 PCI 归属 ==="
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
echo "=== 00:08 下所有 PCI 功能 (USB4 块全貌) ==="
lspci | grep -E "^([0-9a-f]+:)*c[0-9a-f]:" | head -12
lspci -s c6:00 -s c8:00 2>/dev/null | head
lspci -nn -s 00:08.1 -s 00:08.3 2>/dev/null
