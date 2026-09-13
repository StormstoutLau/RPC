#!/bin/bash
# C 站: 深入 — 30.6G VRAM 持有者 + systemd llama 服务看门狗
set +e
echo "=== 1. systemd llama 服务定义 (看门狗配置) ==="
sudo -n systemctl cat llama-server@qwen3.8-27b-mtp.service 2>/dev/null | head -40
echo ""
echo "=== 2. 服务文件位置 ==="
ls -la /etc/systemd/system/llama-server* /etc/systemd/system/llama-instances/ 2>/dev/null
cat /etc/llama-instances/qwen3.8-27b-mtp.env 2>/dev/null | head -20
echo ""
echo "=== 3. VRAM 占用者 — drm 进程 (需要 sudo) ==="
sudo -n cat /sys/kernel/debug/dri/1/drm_gem 2>/dev/null | head -20 || echo '(不可读, 尝试 clients)'
echo ""
echo "=== 4. 检查当前 qwen 进程 (5532) 的 GTT/显存映射 ==="
QPID=5532
ls -l /proc/$QPID/fd 2>/dev/null | grep -iE 'drm|kfd' | head -5
echo "--- 进程 maps 中 amdgpu ---"
grep -iE 'drm|amdgpu|kfd' /proc/$QPID/maps 2>/dev/null | head -5
echo ""
echo "=== 5. KFD 当前进程列表 ==="
sudo -n cat /sys/kernel/debug/kfd/proc_list 2>/dev/null | head -30 || echo '(不可读)'
echo ""
echo "=== 6. 检查是否有残留的 HIP 进程 (来自之前测试) ==="
ps -eo pid,ppid,etime,%cpu,rss,cmd | grep -iE 'llama|hip|rocm' | grep -v grep | head -10
echo ""
echo "=== 7. load 高原因 ==="
top -b -n1 2>/dev/null | awk 'NR>7 && $9>5 {print}' | head -8