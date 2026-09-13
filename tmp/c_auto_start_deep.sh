#!/bin/bash
# C 站: 彻底排查 llama-server 自启来源与显存占用
set +e
echo "========== A. systemd 全量搜索 llama/qwen 关联 =========="
echo "--- A1. 所有 unit 文件 (含 enable 状态) ---"
systemctl list-unit-files 2>/dev/null | grep -iE 'llama|qwen|unsloth|infer|rpc' 
echo "--- A2. 所有 active 服务里 command 含 llama/模型路径 的 ---"
ps -eo pid,ppid,cmd --sort=pid 2>/dev/null | grep -iE 'llama|/models/' | grep -v grep | head -10
echo "--- A3. /etc/systemd/system 全目录 (含 drop-in) ---"
sudo -n find /etc/systemd/system /usr/lib/systemd/system -iname '*llama*' -o -iname '*qwen*' 2>/dev/null | head -20
echo ""
echo "========== B. llama-serve-instance 包装脚本 =========="
cat /usr/local/bin/llama-serve-instance 2>/dev/null | head -40
echo ""
echo "========== C. crontab / user 定时 =========="
crontab -l 2>/dev/null | head -15; echo "---"
sudo -n crontab -l 2>/dev/null | head -10
ls /etc/cron.d/ 2>/dev/null | head -10
echo ""
echo "========== D. bashrc/profile/autostart =========="
grep -iE 'llama|qwen' ~/.bashrc ~/.profile ~/.bash_profile 2>/dev/null | head -10
ls ~/.config/autostart/ 2>/dev/null | head -10
echo ""
echo "========== E. 当前占用显存/GTT 的进程 =========="
sudo -n cat /sys/kernel/debug/dri/1/drm_gem 2>/dev/null | head -30 || echo '(drm_gem 不可读)'
echo "--- kfd proc_list ---"
sudo -n cat /sys/kernel/debug/kfd/proc_list 2>/dev/null | head -30 || echo '(kfd proc_list 不可读)'
echo ""
echo "========== F. 服务重启历史 (journal) =========="
sudo -n journalctl -u 'llama-server@qwen3.8-27b-mtp.service' --no-pager -n 15 2>/dev/null | tail -15
echo ""
echo "========== G. 当前 VRAM/GTT/内存 =========="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
free -g | head -2