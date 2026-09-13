#!/bin/bash
# C 站: 恢复 ROCm + 测试 ROCBLAS_USE_HIPBLASLT=0 workaround
set +e
echo "=== 0. 恢复系统 ROCm ==="
sudo -n mv /opt/rocm-7.2.1.bak-hiptest /opt/rocm-7.2.1 2>/dev/null && echo '已恢复 7.2.1'
ls -d /opt/rocm* 2>/dev/null

echo "=== 1. 清理 ==="
pkill -9 -f 'llama-server.*gpt-oss' 2>/dev/null
pkill -9 -f 'qwen3.8-27b' 2>/dev/null
sleep 2

echo "=== 2. 启动 gpt-oss HIP + ROCBLAS_USE_HIPBLASLT=0 ==="
ROCBLAS_USE_HIPBLASLT=0 setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_hip.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 60
echo "=== 3. 日志尾 ==="
tail -15 /tmp/c_gpt_hip.log
echo "=== 4. 端口 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo 'not yet'
echo "=== 5. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 6. 新 fault ==="
sudo -n dmesg -T 2>/dev/null | grep -A1 'gfxhub. page fault' | tail -4
echo "=== 7. 内存 ==="
free -g | head -2