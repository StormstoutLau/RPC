#!/bin/bash
# C 站: 临时隔离系统 aqlprofile -> 重试 gpt-oss HIP (验证混搭根因, 全程可逆)
set +e
echo "=== 0. 备份并改名系统 aqlprofile ==="
ls -la /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64*
sudo -n mv /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64.so.1.0.70201 /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64.so.1.0.70201.bak-hip-test 2>/dev/null && echo '已改名' || echo '改名失败(可能无sudo权限)'
ls -la /opt/rocm-7.2.1/lib/libhsa-amd-aqlprofile64* 2>/dev/null

echo "=== 1. 清理 ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null; sleep 2

echo "=== 2. 启动 ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_hip.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 55
echo "=== 3. 日志尾 ==="
tail -12 /tmp/c_gpt_hip.log
echo "=== 4. 端口 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo 'not yet'
echo "=== 5. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 6. 是否加载 aqlprofile ==="
grep -c aqlprofile /proc/$PID/maps 2>/dev/null | xargs echo 'maps_aqlprofile_lines='
echo "=== 7. 内存 ==="
free -g | head -2
echo "=== 8. 新 fault ==="
sudo -n dmesg -T 2>/dev/null | tail -4