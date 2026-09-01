#!/bin/bash
# disk_survey.sh — 两站磁盘占用全景
A="scott-lau@10.10.10.1"
echo "############ B 站 ############"
df -h / /data 2>/dev/null | grep -v tmpfs
echo "--- / 顶层大目录 (GB) ---"
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -12
echo "--- /var 细分 ---"
sudo du -xh --max-depth=1 /var 2>/dev/null | sort -rh | head -6
echo "--- journal 占用 ---"
sudo journalctl --disk-usage 2>/dev/null | head -2
echo "--- crash 转储 ---"
sudo du -sh /var/crash 2>/dev/null
echo "--- apt/docker 缓存 ---"
sudo du -sh /var/cache/apt /var/lib/docker 2>/dev/null
echo
echo "############ A 站 ############"
timeout 60 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $A '
  df -h / 2>/dev/null | tail -1
  echo "--- / 顶层大目录 (GB) ---"
  sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -12
  echo "--- /var 细分 ---"
  sudo du -xh --max-depth=1 /var 2>/dev/null | sort -rh | head -6
  echo "--- journal 占用 ---"
  sudo journalctl --disk-usage 2>/dev/null | head -2
  echo "--- crash 转储 ---"
  sudo du -sh /var/crash 2>/dev/null
  echo "--- apt/docker 缓存 ---"
  sudo du -sh /var/cache/apt /var/lib/docker 2>/dev/null
'