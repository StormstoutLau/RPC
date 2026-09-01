#!/bin/bash
# hang_forensic_a2.sh — 补齐缺口: 第一次挂死 boot -6 画像 + IRQ/idle + pstore + rpc-server 日志

echo "########## [1] boot -6 (第一次挂死, 7.0 内核, journal 止于 00:42) ##########"
echo "--- 尾部 15 条 ---"
journalctl -b -6 --no-pager 2>/dev/null | tail -15
echo
echo "--- kernel 可疑模式 ---"
for pat in "userptr|hogged|stall|lockup|blocked for more" "amdgpu.*(error|timeout|reset|fault)" "kfd|amdkfd" "OOM|out of memory|oom-kill" "kswapd|compaction" "thermal|throttle"; do
  echo "· $pat:"
  journalctl -b -6 -k --no-pager 2>/dev/null | grep -iE "$pat" | tail -8
done
echo
echo "--- 00:40-00:42 用户态最后活动 (rpc-server/llama/ksoftirqd) ---"
journalctl -b -6 --no-pager --since "2026-09-01 00:35:00" 2>/dev/null | grep -vE "CRON|pam_unix|No MTA" | tail -25

echo
echo "########## [2] boot -1 (第二次挂死) rpc-server/llama 用户态日志 ##########"
journalctl -b -1 --no-pager -u rpc-server.service 2>/dev/null | tail -10
journalctl -b -1 --no-pager --since "2026-09-01 03:45:00" 2>/dev/null | grep -vE "CRON|pam_unix|No MTA|sysstat" | tail -20

echo
echo "########## [3] pstore (挂死前 console 最后遗言?) ##########"
ls -la /sys/fs/pstore/ 2>/dev/null
cat /sys/fs/pstore/console-ramoops* 2>/dev/null | tail -30 || echo "(pstore 空/不存在)"
journalctl -b 0 -k --no-pager 2>/dev/null | grep -iE "pstore|ramoops|efi.*pstore" | head -5

echo
echo "########## [4] IRQ affinity: 管理网/USB4/GPU 中断分布 ##########"
echo "--- r8169 (管理网) ---"
grep r8169 /proc/interrupts | head -3
echo "--- thunderbolt/usb4 ---"
grep -iE "thunderbolt|xhci.*c8|tb" /proc/interrupts | head -4
echo "--- amdgpu ---"
grep -iE "amdgpu|c5:00" /proc/interrupts | head -6
echo "--- IRQ0 timer / NMI ---"
head -5 /proc/interrupts
echo "--- ksoftirqd CPU 占用 (当前) ---"
ps -eLo pid,comm,pcpu | grep -E "ksoftirqd|kworker.*amdgpu|kfd" | awk '$3>1' | head -10

echo
echo "########## [5] cpuidle 深度统计 (C3 使用量) ##########"
for cpu in 0 4 7; do
  echo "--- cpu$cpu ---"
  for s in /sys/devices/system/cpu/cpu$cpu/cpuidle/state*/; do
    n=$(cat $s/name 2>/dev/null); u=$(cat $s/usage 2>/dev/null); r=$(cat $s/residency 2>/dev/null)
    [ -n "$n" ] && echo "  $n usage=$u residency=${r}us"
  done
done

echo
echo "########## [6] 挂死时内存画像推断: swap/内存配置 ##########"
free -h | head -2
swapon --show 2>/dev/null || echo "(无 swap)"
cat /proc/sys/vm/swappiness 2>/dev/null
echo "--- 当前 GTT 占用 (有服务跑时才非零) ---"
cat /sys/kernel/debug/dri/0/amdgpu_gtt_usage 2>/dev/null || echo "(dri debugfs 需 root/当前无权)"
sudo cat /sys/kernel/debug/dri/0/amdgpu_gtt_usage 2>/dev/null
sudo cat /sys/kernel/debug/dri/0/amdgpu_vram_usage 2>/dev/null

echo
echo "########## [7] 完整 cmdline 来源 (GRUB) ##########"
grep -E "^GRUB_CMDLINE" /etc/default/grub
ls /etc/default/grub.d/ 2>/dev/null
cat /etc/default/grub.d/*.cfg 2>/dev/null | head -10
