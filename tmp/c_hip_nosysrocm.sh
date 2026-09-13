#!/bin/bash
# C 站: 屏蔽系统 ROCm (可逆) -> 重试 gpt-oss HIP, 验证用户态混用是否根因
set +e
echo "=== 0. 备份并屏蔽 /opt/rocm* ==="
ls -d /opt/rocm* 2>/dev/null
if [ -d /opt/rocm-7.2.1 ]; then
  sudo -n mv /opt/rocm-7.2.1 /opt/rocm-7.2.1.bak-hiptest 2>/dev/null && echo '7.2.1 已屏蔽'
fi
if [ -d /opt/rocm ]; then
  # /opt/rocm 是软链到 7.2.1，屏蔽后需替换为空目录抑或一并处理
  ls -la /opt/rocm 2>/dev/null | head -1
fi
echo "--- 若 /opt/rocm 为软链, 一并临时移除 ---"
ls -la /opt/ 2>/dev/null | grep rocm

echo "=== 1. load-gate 60G ==="
bash /tmp/load-gate 60 || { echo GATE FAIL; exit 1; }
echo "=== 2. 清理 ==="
pkill -9 -f 'llama-server.*gpt-oss' 2>/dev/null
pkill -9 -f 'qwen3.8-27b' 2>/dev/null
sleep 2

echo "=== 3. rocminfo 是否仍可用 ==="
rocminfo 2>&1 | head -3 || echo '(无系统 rocm, 省略)'

echo "=== 4. 启动 gpt-oss HIP ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_hip.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 60
echo "=== 5. 日志尾 ==="
tail -15 /tmp/c_gpt_hip.log
echo "=== 6. 端口 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo 'not yet'
echo "=== 7. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 8. /opt rocm 库注入检查 (进程 maps) ==="
grep -c '/opt/rocm' /proc/$PID/maps 2>/dev/null | xargs echo 'maps_opt_rocm_lines='
echo "=== 9. 新 fault ==="
sudo -n dmesg -T 2>/dev/null | grep 'gfxhub. page fault' | tail -2
echo "=== 10. 内存 ==="
free -g | head -2