#!/bin/bash
# C 站: 记录 qwen 服务 -> 停止 -> 重试 gpt-oss HIP -> 冒烟
set +e
QWEN_PID=$(pgrep -f 'qwen3.8-27b-mtp' | head -1)
echo "=== 0. qwen pid=$QWEN_PID cmd 备份 ==="
ps -o cmd -p $QWEN_PID 2>/dev/null > /tmp/c_qwen_cmd.txt
cat /tmp/c_qwen_cmd.txt | head -c 500; echo

echo "=== 1. load-gate 60G ==="
bash /tmp/load-gate 60 || { echo GATE FAIL; exit 1; }

echo "=== 2. 停 qwen Vulkan 服务 (释放 GPU 侧) ==="
kill $QWEN_PID 2>/dev/null
sleep 5
pgrep -f qwen3.8 >/dev/null && echo 'qwen 仍在' || echo 'qwen 已停'
ss -tlnp 2>/dev/null | grep 18080 || echo '(18080 freed)'

echo "=== 3. 清理残留 gpt-oss ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
sleep 2

echo "=== 4. 启动 gpt-oss HIP (A/B 基准参数) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server \
  -m /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf \
  --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none \
  -c 4096 -t 16 --flash-attn on > /tmp/c_gpt_hip.log 2>&1 &
echo "pid=$!"
sleep 45
echo "=== 日志尾部 ==="
tail -15 /tmp/c_gpt_hip.log
echo "=== 端口 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo 'not yet'
echo "=== 新增 page fault? ==="
sudo -n dmesg -T 2>/dev/null | tail -3 | grep -i fault || echo '(无新 fault)'
echo "=== 内存 ==="
free -g | head -2