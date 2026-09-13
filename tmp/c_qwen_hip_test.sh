#!/bin/bash
# C 站: 小模型 qwen3.8-27B HIP 测试 (区分普遍性问题 vs 大模型 GTT 问题)
set +e
MODEL=/home/scott-lau/models/qwen3.8-27b-mtp/Qwen3.8-27B-MTP-Q8_0.gguf
echo "=== 0. load-gate 30G ==="
bash /tmp/load-gate 30 || { echo GATE FAIL; exit 1; }
echo "=== 1. 模型存在? ==="
ls -la $MODEL 2>/dev/null || { echo 无; find / -name 'Qwen3.8-27B*'.gguf -not -path '/proc/*' 2>/dev/null | head -3; exit 1; }
echo "=== 2. 清理 ==="
pkill -9 -f 'llama-server.*gpt-oss' 2>/dev/null
pkill -9 -f 'qwen3.8-27b' 2>/dev/null
sleep 2
echo "=== 3. 启动 qwen3.8 HIP ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m $MODEL --port 18082 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > /tmp/c_qwen_hip.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 30
echo "=== 4. 日志尾 ==="
tail -12 /tmp/c_qwen_hip.log
echo "=== 5. 端口 ==="
ss -tlnp 2>/dev/null | grep 18082 || echo 'not yet'
echo "=== 6. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 7. 新 fault ==="
sudo -n dmesg -T 2>/dev/null | tail -5
echo "=== 8. 内存 ==="
free -g | head -2