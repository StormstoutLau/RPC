#!/bin/bash
# E1 收尾取证: netconsole 全窗 + A 站 journal 满载窗异常扫描
set -u
echo "=== netconsole 全窗内容 (05:49-06:36) ==="
sudo cat /var/log/netconsole-a.log 2>/dev/null
echo "=== 远端 A 站 journal 满载窗 (05:48-06:40) 异常计数 ==="
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'sudo journalctl --since "05:48" --until "06:40" -k --no-pager 2>/dev/null | grep -icE "hogged|gfx_off|amdgpu.*error"; lsmod | grep netconsole; cat /proc/sys/kernel/printk'
echo DONE
