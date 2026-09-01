#!/bin/bash
# diag_b_popup.sh — B 站弹窗错误源排查
echo "=== [1] 系统层近期错误 (apport/crash) ==="
ls -lt /var/crash/ 2>/dev/null | head -4
echo
echo "=== [2] journal 近 10min error 级 ==="
journalctl --since "10 minutes ago" -p err --no-pager | tail -15
echo
echo "=== [3] 桌面弹窗常见源 (update-notifier/apport/gnome) ==="
journalctl --user --since "10 minutes ago" --no-pager 2>/dev/null | grep -iE "error|crash|fail" | tail -8
echo
echo "=== [4] X/会话错误 ==="
journalctl --since "10 minutes ago" --no-pager | grep -iE "gnome-shell|gdm|Xorg" | grep -iE "error|crash|segv" | tail -6
echo
echo "=== [5] 内存/健康速查 ==="
grep -E "MemAvailable" /proc/meminfo
systemctl --failed --no-pager | head -6