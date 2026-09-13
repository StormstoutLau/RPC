#!/bin/bash
# C 站: 诊断卡顿 — 显存占用 + 看门狗拉起 qwen
set +e
echo "=== 1. 系统负载 ==="
uptime
top -b -n1 2>/dev/null | head -12
echo ""
echo "=== 2. VRAM/GTT 占用 ==="
cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null | xargs echo 'vram_used='
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null | xargs echo 'gtt_used='
echo ""
echo "=== 3. 当前所有 llama-server 进程 ==="
ps -eo pid,ppid,etime,%cpu,%mem,rss,cmd | grep -E 'llama-server|ggml' | grep -v grep | head -10
echo ""
echo "=== 4. 系统内存 ==="
free -g | head -3
echo ""
echo "=== 5. 近期 dmesg fault/oom ==="
sudo -n dmesg 2>/dev/null | grep -iE 'page fault|oom|killed process|svm' | tail -8
echo ""
echo "=== 6. systemd 中 qwen/llama 相关服务 (看门狗嫌疑) ==="
systemctl list-units --type=service 2>/dev/null | grep -iE 'qwen|llama|unsloth|rpc|infer' | head -10
echo "--- 所有 unit 文件含 qwen 的 ---"
ls /etc/systemd/system/ 2>/dev/null | head -20
echo ""
echo "=== 7. timer/cron 拉起 qwen 嫌疑 ==="
systemctl list-timers 2>/dev/null | head -10
crontab -l 2>/dev/null | head -10
echo ""
echo "=== 8. 需要 sudo 看 unit 定义 ==="
sudo -n systemctl list-unit-files 2>/dev/null | grep -iE 'qwen|llama|unsloth' | head -10