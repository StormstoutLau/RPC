#!/bin/bash
# hang_forensic_d.sh — 最后补证: sar01 独立数据 + bjork_deepfix 来源
A="scott-lau@10.10.10.1"

echo "########## [1] A 站 sysstat 9-1 数据文件 ##########"
ssh -o ConnectTimeout=10 $A 'ls -la /var/log/sysstat/ | grep -E "sar01|sa01"; echo ---; sadf -d /var/log/sysstat/sar01 -- -u 2>/dev/null | grep -E ";(00:1[0-9]|00:2[0-9]|00:3[0-9]|00:4[0-9])" | head -8'
echo
echo "--- 两次挂死窗口的 sar01 CPU (00:40+, 03:40+) ---"
ssh -o ConnectTimeout=10 $A 'sadf -d /var/log/sysstat/sar01 -- -u 2>/dev/null | grep -E ";(00:[3-5][0-9]|03:[4-5][0-9])" | head -12'
echo
echo "--- 内存 + paging 挂死前 (00:30-00:50) ---"
ssh -o ConnectTimeout=10 $A 'sadf -d /var/log/sysstat/sar01 -- -r -B 2>/dev/null | grep -E ";(00:[3-5][0-9])" | head -10'
echo
echo "########## [2] bjork_deepfix 来源追溯 ##########"
ssh -o ConnectTimeout=10 $A '
  echo "--- crontab 全文 ---"; crontab -l 2>/dev/null
  echo "--- history 中 bjork/fixer 安装痕迹 ---"
  grep -iE "bjork|fixer|deepfix" ~/.bash_history 2>/dev/null | head -10
  echo "--- station_fixer.py 在哪 ---"
  find / -name "station_fixer*" -not -path "/proc/*" 2>/dev/null | head -3
  echo "--- root crontab ---"
  sudo crontab -l 2>/dev/null | head -8'
echo
echo "########## [3] A 站当前 cron 还在跑吗 (脚本已丢) ##########"
ssh -o ConnectTimeout=10 $A 'journalctl -b 0 --no-pager | grep -iE "bjork|No such file" | tail -4'
