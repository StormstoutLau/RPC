#!/bin/bash
# hang_forensic_c.sh — 收敛验证: recover 脚本行为 + sysstat 独立证据 + ppfeaturemask 对比

echo "########## [1] recover_lmstudio_v1.sh 全文 (A 站) ##########"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'cat /tmp/bjork_deepfix/recover_lmstudio_v1.sh 2>/dev/null | head -60'
echo
echo "########## [2] launch_fixer_v2.sh 全文 (A 站) ##########"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'cat /tmp/bjork_deepfix/launch_fixer_v2.sh 2>/dev/null | head -40'
echo
echo "########## [3] recover.log / watchdog.log 内容 (A 站, cron 是否真的触发过拉起) ##########"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 '
  echo "--- watchdog.log (尾部) ---"; tail -10 /tmp/bjork_deepfix/watchdog.log 2>/dev/null
  echo "--- recover.log 全文 ---"; cat /tmp/bjork_deepfix/recover.log 2>/dev/null | tail -30
  echo "--- bjork_deepfix 目录 ---"; ls -la /tmp/bjork_deepfix/ 2>/dev/null'
echo
echo "########## [4] sysstat 独立证据: 挂死前最后采样 (A 站) ##########"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 '
  echo "--- sa01 文件 ---"; ls -la /var/log/sysstat/ 2>/dev/null | tail -5
  echo "--- 第一次挂死前 (00:40-00:50) CPU + 内存 + paging ---"
  sadf -d /var/log/sysstat/sa01 -- -u -r -B -q 2>/dev/null | grep -E "^2026-09-01;00:(4[0-5])" | head -20
  echo "--- 第二次挂死前 (03:40-03:50) ---"
  sadf -d /var/log/sysstat/sa01 -- -u -r -B -q 2>/dev/null | grep -E "^2026-09-01;03:(4[0-9]|50)" | head -15'
echo
echo "########## [5] ppfeaturemask 两站对比 ##########"
echo "--- B 站 ---"
cat /sys/module/amdgpu/parameters/ppfeaturemask 2>/dev/null
echo "--- A 站 ---"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'cat /sys/module/amdgpu/parameters/ppfeaturemask 2>/dev/null'
echo
echo "########## [6] B 站同位置有没有 bjork_deepfix? (确认这是 A 站特有) ##########"
ls /tmp/bjork_deepfix 2>/dev/null || echo "(B 站无 bjork_deepfix — A 站特有)"
crontab -l 2>/dev/null | grep -cE "bjork|fixer|recover" || echo "0"
