#!/bin/bash
# B5p: idle 90s TB 事件观察 (旧线 retimer 振荡对照)
T0=$(sudo dmesg 2>/dev/null | wc -l)
sleep 90
echo "=== 90s idle 期间新增 TB/USB 事件 ==="
sudo dmesg 2>/dev/null | tail -n +$T0 | grep -iE 'thunderbolt|retimer|config error|usb4|bolt' | head -10
echo "(空 = 零事件, 无振荡)"
echo "=== 本次开机累计 config error 总数 ==="
sudo dmesg 2>/dev/null | grep -ic 'config error'
