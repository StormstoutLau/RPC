#!/bin/bash
# hang_forensic_b.sh — B 站对照取证: 两次 A 站挂死时刻 B 站的观察 + B 站自身 gfx off 对照

echo "########## [1] B 站 kernel: 第一次挂死窗口 (00:40-00:58) ##########"
journalctl -k --no-pager --since "2026-09-01 00:40:00" --until "2026-09-01 00:58:00" 2>/dev/null | grep -vE "audit" | head -30
echo
echo "########## [2] B 站 kernel: 第二次挂死窗口 (03:45-03:55) ##########"
journalctl -k --no-pager --since "2026-09-01 03:45:00" --until "2026-09-01 03:55:00" 2>/dev/null | grep -vE "audit" | head -30
echo
echo "########## [3] B 站 llama-server 日志: RPC 断连时刻 ##########"
journalctl --no-pager -u llama-server.service --since "2026-09-01 00:40:00" --until "2026-09-01 01:10:00" 2>/dev/null | tail -15
echo "---"
journalctl --no-pager -u llama-server.service --since "2026-09-01 03:40:00" --until "2026-09-01 04:00:00" 2>/dev/null | tail -15
echo
echo "########## [4] B 站对照: workqueue hogged 报告 (满载下 B 站有没有?) ##########"
journalctl -k --no-pager --since "2026-08-31 14:00:00" 2>/dev/null | grep -iE "hogged|stall|lockup" | head -10
echo "--- B 站同款 amdgpu hogged (gfx off) 对照 ---"
journalctl -k --no-pager 2>/dev/null | grep -iE "gfx_off|gfxoff" | head -10
echo
echo "########## [5] B 站 gfx off 当前状态 ##########"
cat /sys/class/drm/card0/device/gfx_off_enable 2>/dev/null || echo "(gfx_off_enable sysfs 不存在)"
cat /sys/class/drm/card0/device/power_dpm_force_performance_level 2>/dev/null
echo "--- B 站内核 ---"
uname -r
echo
echo "########## [6] A 站 GFXOFF 深挖 (远程) ##########"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 '
  echo "--- A 站 gfx off sysfs ---"
  cat /sys/class/drm/card0/device/gfx_off_enable 2>/dev/null || echo "(gfx_off_enable 不存在)"
  cat /sys/class/drm/card0/device/power_dpm_force_performance_level 2>/dev/null
  echo "--- A 站 amdgpu ppfeaturemask 模块参数 ---"
  cat /sys/module/amdgpu/parameters/ppfeaturemask 2>/dev/null
  echo "--- A 站 bjork_deepfix 是什么 (干扰变量) ---"
  ls -la /tmp/bjork_deepfix/ 2>/dev/null | head -10
  crontab -l 2>/dev/null | grep -E "bjork|fixer|recover" | head -5
  tail -5 /tmp/bjork_deepfix/watchdog.log 2>/dev/null
  tail -8 /tmp/bjork_deepfix/recover.log 2>/dev/null
  echo "--- A 站挂死 boot (-1) 期间 rpc-server 实例日志 ---"
  journalctl -b -1 --no-pager 2>/dev/null | grep -iE "rpc-server|llama" | tail -10
  echo "--- A 站挂死 boot (-6) 期间 rpc-server + LM Studio 拉起记录 ---"
  journalctl -b -6 --no-pager --since "2026-09-01 00:30:00" 2>/dev/null | grep -iE "rpc-server|llama|lm.studio|1234" | tail -10
'
