#!/bin/bash
# hang_forensic_a.sh — A 站挂死 boot 深度取证 (2026-09-01)
# 目标: 两次挂死 (00:57 内核7.0 / 03:51 内核6.17.0-40) 完整画像 + 硬件层证据

echo "########## [0] boot 清单 ##########"
journalctl --list-boots --no-pager | tail -8
CUR=$(journalctl -b 0 --no-pager | head -2 | tail -1 | awk '{print $1" "$2" "$3}')
echo "当前 boot 起始: $CUR"

echo
echo "########## [1] 逐 boot 定位挂死 (最后日志时间 + 尾部异常) ##########"
for b in -1 -2 -3 -4; do
  echo "--- boot $b ---"
  journalctl -b $b --no-pager 2>/dev/null | head -2 | tail -1
  journalctl -b $b --no-pager 2>/dev/null | tail -3
  echo "(boot $b 内核: $(journalctl -b $b -k --no-pager 2>/dev/null | head -1))"
  echo
done

echo "########## [2] 挂死 boot (-1, 疑 03:51 那次) 静默点分析 ##########"
LAST=$(journalctl -b -1 --no-pager 2>/dev/null | tail -1)
echo "最后一条: $LAST"
# 挂死前 60s 的全部日志 (找异常前兆)
LASTTS=$(journalctl -b -1 --no-pager -o short-unix 2>/dev/null | tail -1 | awk '{print $1}' | cut -d. -f1)
if [ -n "$LASTTS" ]; then
  echo "--- 挂死前 90s 日志 (ts > $((LASTTS-90))) ---"
  journalctl -b -1 --no-pager --since "@$((LASTTS-90))" 2>/dev/null | tail -40
fi

echo
echo "########## [3] 挂死 boot 内核日志: 可疑模式扫描 ##########"
for pat in "amdkfd\|kfd" "restore_userptr\|userptr" "hogged\|stall\|blocked" "amdgpu.*error\|amdgpu.*timeout\|GPU reset\|ring.*timeout\|gfx.*timeout" "thermal\|temperature\|overheat" "MCE\|machine check\|Hardware Error\|ras\|EDAC" "rcu\|sched.*stall\|soft lockup\|hard lockup\|NMI" "uvd\|vce\|sdma.*error\|page fault\|VM fault\|GPUVM" "power\|psys\|svi\|current limit"; do
  echo "--- pattern: $pat ---"
  journalctl -b -1 -k --no-pager 2>/dev/null | grep -iE "$pat" | tail -12
done

echo
echo "########## [4] 第一次挂死 boot (-2 或 -3, 00:57 内核 7.0) 同模式对比 ##########"
for b in -2 -3; do
  K=$(journalctl -b $b -k --no-pager 2>/dev/null | grep -m1 "Linux version" | awk '{print $3}')
  T=$(journalctl -b $b --no-pager 2>/dev/null | tail -1 | awk '{print $1" "$2" "$3}')
  echo "--- boot $b (内核 $K, 尾 $T) ---"
  journalctl -b $b -k --no-pager 2>/dev/null | grep -iE "userptr|hogged|stall|lockup|GPU reset|timeout|fault" | tail -10
done

echo
echo "########## [5] 硬件错误层: RAS/MCE/EDAC (跨所有 boot) ##########"
journalctl --no-pager -k 2>/dev/null | grep -iE "mce|machine check|hardware error|edac|ras|corrected error|uncorrected" | tail -15
echo "--- /sys RAS ---"
ls /sys/kernel/debug/ras/ 2>/dev/null || echo "(ras debugfs 不可见)"
dmesg | grep -iE "ras|mce|edac" | tail -8
which rasdaemon && systemctl is-active rasdaemon 2>/dev/null || echo "(rasdaemon 未装)"

echo
echo "########## [6] 当前硬件状态基线 (运行 boot) ##########"
echo "--- CPU idle driver / C-state ---"
cat /sys/devices/system/cpu/cpu0/cpuidle/state*/name 2>/dev/null
cat /sys/devices/system/cpu/cpuidle/current_driver 2>/dev/null
cat /sys/devices/system/cpu/cpuidle/current_governor 2>/dev/null
grep -m2 "cpu MHz\|amd_pstate" /proc/cpuinfo 2>/dev/null
cat /sys/devices/system/cpu/amd_pstate/status 2>/dev/null
echo "--- 温度 ---"
for z in /sys/class/thermal/thermal_zone*/; do
  t=$(cat $z/temp 2>/dev/null); n=$(cat $z/type 2>/dev/null)
  [ -n "$t" ] && echo "$n: $((t/1000))C"
done
echo "--- amdgpu 版本/GTT ---"
journalctl -b 0 -k --no-pager 2>/dev/null | grep -iE "amdgpu.*version|vram|gtt" | head -6
cat /sys/module/amdgpu/parameters/gttsize 2>/dev/null && echo "(gttsize 模块参数)"

echo
echo "########## [7] 0xCF9 复位源判定 ##########"
echo "--- 当前 boot 前的上次关机原因 ---"
LASTBOOT_END=$(journalctl -b -1 --no-pager 2>/dev/null | tail -1 | awk '{print $1" "$2" "$3}')
echo "boot -1 结束于: $LASTBOOT_END"
journalctl -b -1 --no-pager 2>/dev/null | grep -iE "shutdown|reboot|power|systemd-shutdown" | tail -5
echo "--- boot 0 起始的 dmesg (固件级线索) ---"
journalctl -b 0 -k --no-pager 2>/dev/null | grep -iE "BIOS|ACPI.*reset|warm reset|cold reset|0xcf9|reboot" | head -8
